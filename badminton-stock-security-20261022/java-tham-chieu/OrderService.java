package com.sports.service;

import com.sports.dto.OrderCreateRequest;
import com.sports.dto.OrderItemRequest;
import com.sports.dto.OrderItemResponse;
import com.sports.dto.OrderResponse;
import com.sports.dto.OrderCreationResult;
import com.sports.dto.VoucherValidateRequest;
import com.sports.dto.VoucherValidateResponse;
import com.sports.entity.*;
import com.sports.exception.BadRequestException;
import com.sports.exception.InsufficientStockException;
import com.sports.exception.ResourceNotFoundException;
import com.sports.exception.UnauthorizedException;
import com.sports.exception.IdempotencyConflictException;
import org.springframework.dao.DataIntegrityViolationException;
import com.sports.repository.OrderRepository;
import com.sports.repository.ProductRepository;
import com.sports.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import jakarta.persistence.EntityManager;
import jakarta.persistence.LockModeType;

import java.math.BigDecimal;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Slf4j
public class OrderService {

    private final OrderRepository orderRepository;
    private final ProductRepository productRepository;
    private final UserRepository userRepository;
    private final PayOSService payosService;
    private final VoucherService voucherService;
    private final EntityManager entityManager;
    private final PaymentTransitionGuard transitionGuard;

    private static final int MAX_PENDING_ORDERS_PER_USER = 3;
    private static final int ORDER_TIMEOUT_MINUTES = 15;

    @Transactional
    public OrderCreationResult createOrder(Long userId, OrderCreateRequest request, String idempotencyKey) {
        String key = OrderRequestFingerprint.validateKey(idempotencyKey);
        if (request == null) throw new BadRequestException("Dữ liệu đơn hàng không hợp lệ");
        User user = lockOrderingUser(userId);
        String hash = OrderRequestFingerprint.hash(request);
        var existing = orderRepository.findByUserIdAndIdempotencyKey(userId, key);
        if (existing.isPresent()) {
            Order order = existing.get();
            if (!hash.equals(order.getRequestHash())) throw new IdempotencyConflictException();
            return new OrderCreationResult(toDto(order), true);
        }
        validatePendingLimit(userId);
        return new OrderCreationResult(createNewOrder(user, request, key, hash), false);
    }

    private OrderResponse createNewOrder(User user, OrderCreateRequest request, String key, String hash) {
        validateRequestedItems(request.getItems());
        validateOrderInput(request);
        Order order = buildOrder(user, request, normalizePaymentMethod(request.getPaymentMethod()));
        order.setIdempotencyKey(key);
        order.setRequestHash(hash);
        order.setItems(prepareItems(order, request.getItems()));
        calculateOrderTotal(order, request.getVoucherCode());
        applyLoyalty(order, request.getRedeemPoints());
        reserveItems(order.getItems());
        Order saved = saveNewOrder(order);
        if ("PAYOS_VIETQR".equals(order.getPaymentMethod())) {
            saved.setPayosOrderCode(Math.addExact(1_000_000_000L, saved.getId()));
        }
        log.info("Tạo đơn ID={}, phương thức={}, tổng tiền={}", saved.getId(),
                saved.getPaymentMethod(), saved.getTotalAmount());
        return toDto(saved);
    }

    private User lockOrderingUser(Long userId) {
        return userRepository.findByIdForUpdate(userId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy người dùng: " + userId));
    }

    private void validatePendingLimit(Long userId) {
        if (orderRepository.countByUserIdAndStatus(userId, OrderStatus.PENDING) >= MAX_PENDING_ORDERS_PER_USER) {
            throw new BadRequestException("Bạn đang có 3 đơn hàng chưa thanh toán hoặc chờ xử lý");
        }
    }

    private Order saveNewOrder(Order order) {
        try {
            return orderRepository.saveAndFlush(order);
        } catch (DataIntegrityViolationException ex) {
            if (!isIdempotencyConstraint(ex)) throw ex;
            throw new IdempotencyConflictException();
        }
    }

    private boolean isIdempotencyConstraint(Throwable exception) {
        for (Throwable cause = exception; cause != null; cause = cause.getCause()) {
            if (cause instanceof org.hibernate.exception.ConstraintViolationException violation
                    && violation.getConstraintName() != null
                    && violation.getConstraintName().contains("uk_orders_user_idempotency")) return true;
        }
        return false;
    }

    private void validateRequestedItems(List<OrderItemRequest> items) {
        if (items == null || items.isEmpty() || items.size() > 100) {
            throw new BadRequestException("Đơn hàng phải có từ 1 đến 100 dòng sản phẩm");
        }
        java.util.Map<Long, Integer> quantities = new java.util.HashMap<>();
        for (OrderItemRequest item : items) {
            if (item == null || item.getProductId() == null || item.getQuantity() == null
                    || item.getProductId() <= 0 || item.getQuantity() <= 0 || item.getQuantity() > 100) {
                throw new BadRequestException("Sản phẩm và số lượng đặt mua không hợp lệ");
            }
            int total = quantities.merge(item.getProductId(), item.getQuantity(), Integer::sum);
            if (total > 100) throw new BadRequestException("Tổng số lượng mỗi sản phẩm tối đa là 100");
            validateText(item.getSelectedSize(), 50, false);
            validateText(item.getSelectedColor(), 200, false);
            validateText(item.getSelectedWeight(), 50, false);
            validateText(item.getStringingService(), 100, false);
            validateText(item.getStringTension(), 50, false);
        }
    }

    private void validateOrderInput(OrderCreateRequest request) {
        validateText(request.getCustomerName(), 100, true);
        validateText(request.getShippingPhone(), 20, true);
        if (!request.getShippingPhone().matches("^(\\+84|0)[35789][0-9]{8}$")) {
            throw new BadRequestException("Số điện thoại không đúng định dạng Việt Nam");
        }
        if (request.getShippingAddress() == null || request.getShippingAddress().isBlank()) {
            throw new BadRequestException("Địa chỉ nhận hàng không được để trống");
        }
        validateText(request.getNote(), 2000, false);
        validateText(request.getVoucherCode(), 50, false);
        validateText(request.getPaymentMethod(), 50, false);
        if (request.getShippingFee() != null) VndAmount.requireValid(request.getShippingFee());
    }

    private void validateText(String value, int maxLength, boolean required) {
        if (required && (value == null || value.isBlank()) || value != null && value.length() > maxLength) {
            throw new BadRequestException("Trường dữ liệu bắt buộc hoặc độ dài không hợp lệ");
        }
    }

    private Order buildOrder(User user, OrderCreateRequest request, String paymentMethod) {
        LocalDateTime now = LocalDateTime.now();
        return Order.builder().user(user).customerName(request.getCustomerName())
                .shippingPhone(request.getShippingPhone()).shippingAddress(request.getShippingAddress())
                .totalAmount(BigDecimal.ZERO).status(OrderStatus.PENDING).paymentMethod(paymentMethod)
                .expiresAt("COD".equals(paymentMethod) ? null : now.plusMinutes(ORDER_TIMEOUT_MINUTES))
                .note(request.getNote()).createdAt(now).build();
    }

    private List<OrderItem> prepareItems(Order order, List<OrderItemRequest> requests) {
        java.util.Map<Long, Integer> quantities = new java.util.TreeMap<>();
        requests.forEach(item -> quantities.merge(item.getProductId(), item.getQuantity(), Integer::sum));
        java.util.Map<Long, Product> products = new java.util.HashMap<>();
        quantities.forEach((id, quantity) -> {
            Product product = lockProduct(id);
            validateProductForOrder(product, quantity);
            products.put(id, product);
        });
        return requests.stream().sorted(Comparator.comparing(OrderItemRequest::getProductId))
                .map(item -> prepareItem(order, item, products.get(item.getProductId())))
                .collect(Collectors.toList());
    }

    private void validateProductForOrder(Product product, int quantity) {
        if (!Boolean.TRUE.equals(product.getCatalogVisible())) {
            throw new BadRequestException("Sản phẩm '" + product.getName() + "' đã được ẩn khỏi cửa hàng");
        }
        if (product.getStock() < quantity) {
            throw new InsufficientStockException("Sản phẩm '" + product.getName() + "' không đủ tồn kho");
        }
        VndAmount.requireValid(product.getPrice());
        if (product.getPrice().signum() == 0) throw new BadRequestException("Giá sản phẩm không hợp lệ");
        long reservedStock = (long) product.getReservedStock() + quantity;
        if (reservedStock > Integer.MAX_VALUE) {
            throw new BadRequestException("Tồn kho giữ chỗ vượt giới hạn cho phép");
        }
    }

    private OrderItem prepareItem(Order order, OrderItemRequest request, Product product) {
        ProductVariant variant = ProductVariantService.select(product, request);
        return OrderItem.builder().order(order).product(product).quantity(request.getQuantity())
                .variant(variant).price(product.getPrice()).selectedSize(variant == null ? request.getSelectedSize() : variant.getSize())
                .selectedColor(variant == null ? request.getSelectedColor() : variant.getColor())
                .selectedWeight(variant == null ? request.getSelectedWeight() : variant.getWeightGrip())
                .stringingService(request.getStringingService()).stringTension(request.getStringTension()).build();
    }

    private void reserveItems(List<OrderItem> items) {
        for (OrderItem item : items) {
            Product product = item.getProduct();
            ProductVariantService.reserve(item.getVariant(), item.getQuantity());
            product.setStock(product.getStock() - item.getQuantity());
            product.setReservedStock(product.getReservedStock() + item.getQuantity());
            ProductVariantService.refreshTotals(product);
            productRepository.save(product);
        }
    }

    private BigDecimal calculateSubtotal(List<OrderItem> items) {
        BigDecimal subtotal = BigDecimal.ZERO;
        for (OrderItem item : items) {
            BigDecimal lineTotal = VndAmount.requireValid(
                    item.getPrice().multiply(BigDecimal.valueOf(item.getQuantity())));
            subtotal = VndAmount.requireValid(subtotal.add(lineTotal));
        }
        return subtotal;
    }

    private void calculateOrderTotal(Order order, String voucherCode) {
        BigDecimal subtotal = calculateSubtotal(order.getItems());
        BigDecimal shippingFee = VoucherService.quoteShipping(subtotal);
        BigDecimal discount = BigDecimal.ZERO;
        if (voucherCode != null && !voucherCode.isBlank()) {
            VoucherValidateResponse voucher = voucherService.reserveVoucher(
                    new VoucherValidateRequest(voucherCode.trim(), subtotal, order.getItems().stream()
                            .map(item -> new OrderItemRequest(item.getProduct().getId(), item.getQuantity())).toList()));
            discount = VndAmount.requireValid(voucher.getDiscountAmount());
            if (voucher.getFinalShippingFee() != null) shippingFee = VndAmount.requireValid(voucher.getFinalShippingFee());
            order.setVoucherCode(voucher.getCode());
        }
        BigDecimal discountedSubtotal = VndAmount.requireValid(subtotal.subtract(discount));
        order.setDiscountAmount(VndAmount.requireValid(discount));
        order.setShippingFee(VndAmount.requireValid(shippingFee));
        order.setTotalAmount(VndAmount.requireValid(discountedSubtotal.add(shippingFee)));
    }

    private String normalizePaymentMethod(String value) {
        String method = value == null || value.isBlank() ? "PAYOS_VIETQR" : value.trim();
        if (!"COD".equals(method) && !"PAYOS_VIETQR".equals(method)) {
            throw new BadRequestException("Phương thức thanh toán chưa được hỗ trợ");
        }
        return method;
    }

    private void applyLoyalty(Order order, Integer requestedPoints) {
        if (requestedPoints == null || requestedPoints == 0) return;
        if (requestedPoints < 0 || requestedPoints > 1000000) throw new BadRequestException("Số điểm không hợp lệ");
        Long userId = order.getUser().getId();
        var recognized = orderRepository.findRecognizedPaymentOrders().stream()
                .filter(o -> o.getUser().getId().equals(userId)).map(Order::getId).collect(Collectors.toSet());
        long available = LoyaltyPolicy.available(orderRepository.findByUserIdOrderByCreatedAtDesc(userId),recognized);
        BigDecimal amount = LoyaltyPolicy.discount(requestedPoints,available,order.getTotalAmount().subtract(order.getShippingFee()));
        order.setPointsUsed(requestedPoints);order.setPointsDiscount(amount);
        order.setTotalAmount(VndAmount.requireValid(order.getTotalAmount().subtract(amount)));
    }

    private Order lockOrder(Long orderId) {
        return orderRepository.findByIdForUpdate(orderId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy đơn hàng: " + orderId));
    }

    private Product lockProduct(Long productId) {
        entityManager.flush();
        Product product = productRepository.findByIdForUpdate(productId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy sản phẩm: " + productId));
        entityManager.refresh(product, LockModeType.PESSIMISTIC_WRITE);
        return product;
    }

    @Transactional
    public OrderResponse cancelOrder(Long orderId, Long currentUserId, boolean isAdmin) {
        Order order = lockOrder(orderId);
        if (!isAdmin && !order.getUser().getId().equals(currentUserId)) {
            throw new UnauthorizedException("Bạn không có quyền thao tác trên đơn hàng này!");
        }
        if (order.getStatus() == OrderStatus.CANCELLED) return toDto(order);
        transitionGuard.checkCancel(order);
        cancelPendingOrder(order);
        return toDto(orderRepository.save(order));
    }

    private void cancelPendingOrder(Order order) {
        if (order.getStatus() != OrderStatus.PENDING) {
            throw new BadRequestException("Chỉ được hủy đơn chưa thanh toán và chưa giao hàng");
        }
        settleReservedStock(order, true);
        voucherService.releaseVoucher(order.getVoucherCode());
        order.setStatus(OrderStatus.CANCELLED);
        CheckoutRevision.touch(order);
    }

    private void settleReservedStock(Order order, boolean restoreAvailable) {
        List<OrderItem> items = order.getItems().stream()
                .sorted(Comparator.comparing(item -> item.getProduct().getId())).toList();
        for (OrderItem item : items) {
            Product product = lockProduct(item.getProduct().getId());
            if (product.getReservedStock() < item.getQuantity()) {
                throw new BadRequestException("Tồn kho giữ chỗ không khớp; cần kiểm tra trước khi xử lý đơn");
            }
            product.setReservedStock(product.getReservedStock() - item.getQuantity());
            if (restoreAvailable) product.setStock(product.getStock() + item.getQuantity());
            ProductVariantService.settle(item.getVariant(), item.getQuantity(), restoreAvailable);
            ProductVariantService.refreshTotals(product);
            productRepository.save(product);
        }
    }

    @Transactional
    public boolean expireOrder(Long orderId) {
        Order order = lockOrder(orderId);
        if (order.getStatus() != OrderStatus.PENDING || !"PAYOS_VIETQR".equals(order.getPaymentMethod())
                || order.getExpiresAt() == null || order.getExpiresAt().isAfter(LocalDateTime.now())) {
            return false;
        }
        transitionGuard.expired(order);
        cancelPendingOrder(order);
        orderRepository.save(order);
        return true;
    }

    @Transactional
    public void handlePaymentSuccess(Long payosOrderCode, BigDecimal amount) {
        Order order = orderRepository.findByPayosOrderCodeForUpdate(payosOrderCode)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy đơn hàng với mã PayOS"));
        validatePayment(order, amount);
        if (order.getStatus() == OrderStatus.PAID || order.getStatus() == OrderStatus.SHIPPING
                || order.getStatus() == OrderStatus.COMPLETED) return;
        if (order.getStatus() != OrderStatus.PENDING || order.getExpiresAt() == null
                || !order.getExpiresAt().isAfter(LocalDateTime.now())) {
            log.warn("Thanh toán đến cho đơn đã hủy/hết hạn ID={}; cần đối soát thủ công", order.getId());
            throw new BadRequestException("Đơn đã hủy hoặc hết hạn; cần đối soát thanh toán thủ công");
        }
        settleReservedStock(order, false);
        order.setStatus(OrderStatus.PAID);
        CheckoutRevision.touch(order);
        orderRepository.save(order);
    }

    private void validatePayment(Order order, BigDecimal amount) {
        VndAmount.requireValid(amount);
        VndAmount.requireValid(order.getTotalAmount());
        if (!"PAYOS_VIETQR".equals(order.getPaymentMethod())) {
            throw new BadRequestException("Đơn hàng không sử dụng PayOS");
        }
        if (amount == null || amount.signum() < 0 || order.getTotalAmount().compareTo(amount) != 0) {
            throw new BadRequestException("Số tiền thanh toán không khớp với đơn hàng!");
        }
    }

    /**
     * Get order details with strict Anti-IDOR protection.
     */
    @Transactional(readOnly = true)
    public OrderResponse getOrderById(Long orderId, Long currentUserId, boolean isAdmin) {
        Order order = orderRepository.findById(orderId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy đơn hàng với ID: " + orderId));

        // Anti-IDOR check
        if (!isAdmin && !order.getUser().getId().equals(currentUserId)) {
            throw new UnauthorizedException("Bạn không có quyền truy cập vào đơn hàng này!");
        }

        return toDto(order);
    }

    @Transactional(readOnly = true)
    public List<OrderResponse> getUserOrders(Long userId) {
        return orderRepository.findByUserIdOrderByCreatedAtDesc(userId).stream()
                .map(this::toDto)
                .collect(Collectors.toList());
    }

    @Transactional(readOnly = true)
    public List<OrderResponse> getAllOrders() {
        return orderRepository.findAllByOrderByCreatedAtDesc().stream()
                .map(this::toDto)
                .collect(Collectors.toList());
    }

    @Transactional
    public OrderResponse updateOrderStatus(Long orderId, OrderStatus newStatus) {
        return updateOrderStatus(orderId, newStatus, null);
    }

    @Transactional
    public OrderResponse updateOrderStatus(Long orderId, OrderStatus newStatus, PayOSPaymentClient.Query proof) {
        Order order = lockOrder(orderId);
        if (newStatus == order.getStatus()) return toDto(order);
        transitionGuard.checkDelivery(order, newStatus, proof);
        if (newStatus == OrderStatus.CANCELLED) {
            transitionGuard.checkCancel(order);
            cancelPendingOrder(order);
        } else if (newStatus == OrderStatus.SHIPPING && canShip(order)) {
            if ("COD".equals(order.getPaymentMethod())) settleReservedStock(order, false);
            order.setStatus(newStatus);
        } else if (newStatus == OrderStatus.COMPLETED && order.getStatus() == OrderStatus.SHIPPING) {
            if ("COD".equals(order.getPaymentMethod()) && order.getCashCollectedAt() == null) {
                throw new BadRequestException("Cần xác nhận đã thu tiền mặt/COD trước khi hoàn tất đơn");
            }
            order.setStatus(newStatus);
            order.setCompletedAt(LocalDateTime.now());
        } else {
            throw new BadRequestException("Không được chuyển trạng thái đơn hàng theo luồng này");
        }
        CheckoutRevision.touch(order);
        return toDto(orderRepository.save(order));
    }

    private boolean canShip(Order order) {
        return ("COD".equals(order.getPaymentMethod()) && order.getStatus() == OrderStatus.PENDING)
                || ("PAYOS_VIETQR".equals(order.getPaymentMethod()) && order.getStatus() == OrderStatus.PAID);
    }

    OrderResponse snapshot(Order order) {
        return toDto(order);
    }

    private OrderResponse toDto(Order order) {
        long secondsRemaining = 0;
        if (order.getStatus() == OrderStatus.PENDING && order.getExpiresAt() != null) {
            Duration duration = Duration.between(LocalDateTime.now(), order.getExpiresAt());
            secondsRemaining = Math.max(0, duration.getSeconds());
        }

        List<OrderItemResponse> itemResponses = order.getItems().stream()
                .map(item -> {
                    BigDecimal price = item.getPrice() != null ? item.getPrice() : BigDecimal.ZERO;
                    int qty = item.getQuantity() != null ? item.getQuantity() : 1;
                    return OrderItemResponse.builder()
                            .id(item.getId())
                            .productId(item.getProductIdSnapshot() != null ? item.getProductIdSnapshot() : item.getProduct() != null ? item.getProduct().getId() : null)
                            .productName(item.getProductNameSnapshot() != null ? item.getProductNameSnapshot() : item.getProduct() != null ? item.getProduct().getName() : "Sản phẩm đã ngừng bán")
                            .productSku(item.getProductSkuSnapshot()).productDeleted(item.getProduct()==null)
                            .productBrand(item.getProductBrandSnapshot() != null ? item.getProductBrandSnapshot() : item.getProduct() != null ? item.getProduct().getBrand() : "")
                            .categoryIdSnapshot(item.getCategoryIdSnapshot())
                            .productImageUrl(null)
                            .weightGrip(item.getProduct() != null ? item.getProduct().getWeightGrip() : "")
                            .selectedSize(item.getSelectedSize())
                            .selectedColor(item.getSelectedColor())
                            .selectedWeight(item.getSelectedWeight())
                            .stringingService(item.getStringingService())
                            .stringTension(item.getStringTension())
                            .quantity(qty)
                            .price(price)
                            .subtotal(price.multiply(BigDecimal.valueOf(qty)))
                            .build();
                })
                .collect(Collectors.toList());

        return OrderResponse.builder()
                .id(order.getId())
                .userId(order.getUser().getId())
                .customerName(order.getCustomerName())
                .shippingPhone(order.getShippingPhone())
                .shippingAddress(order.getShippingAddress())
                .totalAmount(order.getTotalAmount())
                .shippingFee(order.getShippingFee() != null ? order.getShippingFee() : BigDecimal.ZERO)
                .voucherCode(order.getVoucherCode())
                .discountAmount(order.getDiscountAmount() != null ? order.getDiscountAmount() : BigDecimal.ZERO)
                .pointsUsed(order.getPointsUsed()).pointsDiscount(order.getPointsDiscount())
                .note(order.getNote())
                .status(order.getStatus().name())
                .paymentMethod(order.getPaymentMethod())
                .payosOrderCode(order.getPayosOrderCode())
                .expiresAt(order.getExpiresAt())
                .timeRemainingSeconds(secondsRemaining)
                .createdAt(order.getCreatedAt())
                .completedAt(order.getCompletedAt())
                .cashCollected(order.getCashCollectedAt() != null)
                .cashCollectedAt(order.getCashCollectedAt())
                .cashCollectedBy(order.getCashCollectedBy())
                .items(itemResponses)
                .build();
    }
}
