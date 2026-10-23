package com.sports.service;

import com.sports.entity.*;
import com.sports.dto.*;
import com.sports.exception.*;
import com.sports.repository.*;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.*;

@Service @RequiredArgsConstructor
public class ProductVariantService {
    private final ProductRepository products;
    private final ProductVariantRepository variants;

    static List<ProductVariantDto> normalizeImportVariants(ProductDto dto) {
        var product=Product.builder().sku(dto.getSku()).stock(Objects.requireNonNullElse(dto.getStock(),0))
                .colorName(dto.getColorName()).quantityPerPack(dto.getQuantityPerPack()).weightGrip(dto.getWeightGrip())
                .availableSizes(dto.getAvailableSizes()).category(dto.getCategoryId()==null ? null
                        : Category.builder().id(dto.getCategoryId()).build()).build();
        initialize(product,dto);
        return product.getVariants().stream().map(ProductVariantService::importVariant).toList();
    }

    private static ProductVariantDto importVariant(ProductVariant variant) {
        return ProductVariantDto.builder().color(variant.getColor()).size(variant.getSize())
                .weightGrip(variant.getWeightGrip()).packaging(variant.getPackaging())
                .stock(variant.getStock()).active(variant.getActive()).build();
    }

    public static void initialize(Product product, ProductDto dto) {
        List<ProductVariantDto> requested=dto.getVariants();
        if (requested == null || requested.isEmpty()) requested=defaultVariants(product);
        if (requested.size()>1000) throw new BadRequestException("Mỗi sản phẩm tối đa 1.000 biến thể");
        List<ProductVariant> created=new ArrayList<>();
        Set<List<String>> unique=new HashSet<>();
        for (var input : requested) {
            var variant=newVariant(product,input,product.getSku()+String.format(Locale.ROOT,"-V%03d",created.size()+1));
            if (variant.getColor()==null) variant.setColor(clean(product.getColorName()));
            if (variant.getPackaging()==null) variant.setPackaging(clean(product.getQuantityPerPack()));
            validateSingleColor(variant.getColor());
            if (!unique.add(combination(variant))) throw new BadRequestException("Biến thể bị trùng");
            created.add(variant);
        }
        validateChoiceLengths(product,created);
        product.getVariants().addAll(created);
        refreshCatalog(product);
    }

    private static ProductVariant newVariant(Product product, ProductVariantDto input, String sku) {
        if (input==null || input.getId()!=null || input.getSku()!=null && !input.getSku().isBlank()
                || Boolean.TRUE.equals(input.getLegacy()) || input.getReservedStock()!=null && input.getReservedStock()!=0)
            throw new BadRequestException("ID, SKU và hàng giữ chỗ của biến thể do hệ thống quản lý");
        validateStock(input.getStock());
        var normalized=ProductVariantDto.builder().color(clean(input.getColor())).size(clean(input.getSize()))
                .weightGrip(clean(input.getWeightGrip())).packaging(clean(input.getPackaging())).build();
        validateAttributes(product,normalized);
        return ProductVariant.builder().product(product).sku(sku).color(normalized.getColor()).size(normalized.getSize())
                .weightGrip(normalized.getWeightGrip()).packaging(normalized.getPackaging()).stock(input.getStock())
                .reservedStock(0).active(!Boolean.FALSE.equals(input.getActive())).legacy(false).build();
    }

    private static void validateStock(Integer stock) {
        if (stock==null || stock<0 || stock>1000000) throw new BadRequestException("Tồn biến thể phải từ 0 đến 1.000.000");
    }

    private static String clean(String value) {
        return value==null || value.isBlank() ? null : value.trim();
    }

    private static List<String> combination(ProductVariant variant) {
        return java.util.stream.Stream.of(variant.getColor(),variant.getSize(),variant.getWeightGrip(),variant.getPackaging())
                .map(value->Objects.toString(clean(value),"").toLowerCase(Locale.ROOT)).toList();
    }

    private static void validateAttributes(Product product, ProductVariantDto input) {
        validateLength(input.getColor(),200,"Màu sắc");validateLength(input.getSize(),50,"Kích cỡ");
        validateLength(input.getWeightGrip(),50,"Trọng lượng/cỡ cán");validateLength(input.getPackaging(),100,"Quy cách");
        validateSingleColor(input.getColor());
        validateSize(product,input);
    }

    private static void validateSingleColor(String color) {
        if (color!=null && (color.contains(";") || color.contains(",") || color.contains("…")
                || color.matches("(?s).*\\.\\s*\\.\\s*\\..*")))
            throw new BadRequestException("Mỗi biến thể chỉ có một màu hoặc một màu phối. Tách danh sách màu thành các biến thể riêng; không nhập dấu ba chấm.");
    }

    private static void validateLength(String text,int maximum,String label) {
        if (text!=null && text.length()>maximum) throw new BadRequestException(label+" vượt quá "+maximum+" ký tự");
    }

    private static void validateSize(Product product,ProductVariantDto input) {
        if (product.getCategory()==null) return;
        if (product.getCategory().getId()==2 && (input.getSize()==null || !input.getSize().matches("(?:3[5-9]|4[0-2])(?:\\.5)?")
                || Double.parseDouble(input.getSize())>42)) throw new BadRequestException("Size giày chỉ từ 35 đến 42");
        if (product.getCategory().getId()==3 && (input.getSize()==null || input.getSize().isBlank())) throw new BadRequestException("Quần áo cần kích cỡ");
        if (product.getCategory().getId()==1 && (input.getWeightGrip()==null || input.getWeightGrip().isBlank())) throw new BadRequestException("Vợt cần trọng lượng/cỡ cán");
    }

    private static List<ProductVariantDto> defaultVariants(Product product) {
        List<String> sizes=new ArrayList<>();
        if (product.getAvailableSizes()!=null) try {
            var node=new com.fasterxml.jackson.databind.ObjectMapper().readTree(product.getAvailableSizes());
            node.forEach(size -> sizes.add(size.asText()));
        } catch(Exception ex) { throw new BadRequestException("Danh sách kích cỡ không hợp lệ"); }
        if (sizes.isEmpty()) sizes.add(null);
        List<ProductVariantDto> result=new ArrayList<>();
        int total=product.getStock();
        for (int index=0;index<sizes.size();index++) result.add(ProductVariantDto.builder().size(sizes.get(index))
                .color(product.getColorName()).weightGrip(product.getWeightGrip()).packaging(product.getQuantityPerPack())
                .stock(total/sizes.size()+(index<total%sizes.size()?1:0)).build());
        return result;
    }

    public static List<ProductVariantDto> describe(Product product) {
        if (product.getVariants() == null) return List.of();
        return product.getVariants().stream().map(v -> ProductVariantDto.builder().id(v.getId()).sku(v.getSku())
                .color(v.getColor()).size(v.getSize()).weightGrip(v.getWeightGrip()).packaging(v.getPackaging())
                .stock(v.getStock()).reservedStock(v.getReservedStock()).active(v.getActive()).legacy(v.getLegacy())
                .inStock(Boolean.TRUE.equals(v.getActive()) && v.getStock() > 0).build()).toList();
    }

    public static ProductVariant select(Product product, OrderItemRequest request) {
        List<ProductVariant> all = product.getVariants();
        if (all == null || all.isEmpty()) return null;
        var candidates = all.stream().filter(v -> Boolean.TRUE.equals(v.getActive()) && !Boolean.TRUE.equals(v.getLegacy()))
                .filter(v -> request.getVariantId() == null || v.getId().equals(request.getVariantId()))
                .filter(v -> matches(request.getSelectedSize(), v.getSize()) && matches(request.getSelectedColor(), v.getColor())
                        && matches(request.getSelectedWeight(), v.getWeightGrip())).toList();
        if (candidates.size() != 1) throw new BadRequestException("Vui lòng chọn đúng màu, kích cỡ hoặc trọng lượng của sản phẩm");
        return candidates.get(0);
    }
    private static boolean matches(String requested, String actual) {
        return requested == null || requested.isBlank() || requested.trim().equals(actual);
    }
    public static void reserve(ProductVariant variant, int quantity) {
        if (variant == null) return;
        if (variant.getStock() < quantity) throw new InsufficientStockException("Biến thể đã chọn không đủ hàng");
        variant.setStock(variant.getStock() - quantity);
        variant.setReservedStock(Math.addExact(variant.getReservedStock(), quantity));
    }
    public static void settle(ProductVariant variant, int quantity, boolean restore) {
        if (variant == null) return;
        if (variant.getReservedStock() < quantity) throw new BadRequestException("Tồn giữ chỗ của biến thể không khớp");
        variant.setReservedStock(variant.getReservedStock() - quantity);
        if (restore) variant.setStock(Math.addExact(variant.getStock(), quantity));
    }
    public static void refreshTotals(Product product) {
        if (product.getVariants() == null || product.getVariants().isEmpty()) return;
        product.setStock(product.getVariants().stream().filter(v -> Boolean.TRUE.equals(v.getActive()))
                .mapToInt(ProductVariant::getStock).reduce(0, Math::addExact));
        product.setReservedStock(product.getVariants().stream().mapToInt(ProductVariant::getReservedStock).reduce(0, Math::addExact));
    }

    public static void refreshCatalog(Product product) {
        refreshTotals(product);
        var active=activeVariants(product.getVariants());
        validateChoiceLengths(product,active);
        product.setColorName(summary(active,ProductVariant::getColor));
        Long category=product.getCategory()==null ? null : product.getCategory().getId();
        if (Objects.equals(category,1L)) product.setWeightGrip(summary(active,ProductVariant::getWeightGrip));
        if (Objects.equals(category,5L)) product.setQuantityPerPack(summary(active,ProductVariant::getPackaging));
        if (Objects.equals(category,2L) || Objects.equals(category,3L)) {
            try { product.setAvailableSizes(new com.fasterxml.jackson.databind.ObjectMapper()
                    .writeValueAsString(choices(active,ProductVariant::getSize))); }
            catch(com.fasterxml.jackson.core.JsonProcessingException ex) { throw new IllegalStateException(ex); }
        }
    }

    private static List<ProductVariant> activeVariants(List<ProductVariant> values) {
        return values.stream().filter(v->Boolean.TRUE.equals(v.getActive()) && !Boolean.TRUE.equals(v.getLegacy())).toList();
    }

    private static List<String> choices(List<ProductVariant> values,java.util.function.Function<ProductVariant,String> field) {
        Map<String,String> unique=new LinkedHashMap<>();
        for (var variant : values) {
            String value=clean(field.apply(variant));
            if (value!=null) unique.putIfAbsent(value.toLowerCase(Locale.ROOT),value);
        }
        return new ArrayList<>(unique.values());
    }

    private static String summary(List<ProductVariant> values,java.util.function.Function<ProductVariant,String> field) {
        String result=String.join(", ",choices(values,field));
        return result.isEmpty() ? null : result;
    }

    private static void validateChoiceLengths(Product product,List<ProductVariant> values) {
        var active=activeVariants(values);
        validateLength(summary(active,ProductVariant::getColor),200,"Tổng các lựa chọn màu sắc");
        Long category=product.getCategory()==null ? null : product.getCategory().getId();
        if (Objects.equals(category,1L)) validateLength(summary(active,ProductVariant::getWeightGrip),50,"Tổng các lựa chọn trọng lượng/cỡ cán");
        if (Objects.equals(category,5L)) validateLength(summary(active,ProductVariant::getPackaging),50,"Tổng các lựa chọn quy cách");
    }

    @Transactional
    public ProductVariantDto create(Long productId,ProductVariantDto dto) {
        var product=lockedProduct(productId);
        if (product.getCategory()==null) throw new BadRequestException("Cần xác định danh mục trước khi thêm biến thể");
        if (product.getVariants().size()>=1000) throw new BadRequestException("Mỗi sản phẩm tối đa 1.000 biến thể");
        var created=newVariant(product,dto,nextSku(product));
        var key=combination(created);
        if (product.getVariants().stream().anyMatch(v->!Boolean.TRUE.equals(v.getLegacy()) && combination(v).equals(key)))
            throw new BadRequestException("Tổ hợp đã tồn tại. Hãy cập nhật tồn hoặc bật lại biến thể cũ");
        var proposed=new ArrayList<>(product.getVariants());proposed.add(created);
        validateChoiceLengths(product,proposed);
        created=variants.saveAndFlush(created);
        product.getVariants().add(created);refreshCatalog(product);products.saveAndFlush(product);
        return describedVariant(product,created.getId());
    }

    private Product lockedProduct(Long productId) {
        return products.findByIdForUpdate(productId).orElseThrow(()->new ResourceNotFoundException("Không tìm thấy sản phẩm"));
    }

    private String nextSku(Product product) {
        if (product.getSku()==null || product.getSku().isBlank()) throw new BadRequestException("Sản phẩm chưa có SKU hợp lệ");
        int index=product.getVariants().size()+1;
        String sku;
        do { sku=product.getSku()+String.format(Locale.ROOT,"-V%03d",index++); }
        while (variants.existsBySkuIgnoreCase(sku) || containsSku(product,sku));
        return sku;
    }

    private boolean containsSku(Product product,String sku) {
        return product.getVariants().stream().anyMatch(v->sku.equalsIgnoreCase(v.getSku()));
    }

    private ProductVariantDto describedVariant(Product product,Long variantId) {
        return describe(product).stream().filter(v->Objects.equals(v.getId(),variantId)).findFirst().orElseThrow();
    }

    @Transactional
    public ProductVariantDto update(Long productId, Long variantId, ProductVariantDto dto) {
        Product product = lockedProduct(productId);
        var variant = product.getVariants().stream().filter(v -> v.getId().equals(variantId)).findFirst()
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy biến thể của sản phẩm"));
        validateUpdateIdentity(variant,dto);
        validateStock(dto.getStock());
        if (!Objects.equals(dto.getExpectedStock(),variant.getStock()))
            throw new BadRequestException("Tồn kho đã thay đổi. Hãy tải lại trước khi lưu");
        if (Boolean.FALSE.equals(dto.getActive()) && variant.getReservedStock() > 0)
            throw new BadRequestException("Biến thể đang giữ hàng cho đơn chưa hoàn tất");
        if (Boolean.TRUE.equals(dto.getActive())) validateActivation(product,variant);
        variant.setStock(dto.getStock());
        if (dto.getActive() != null) variant.setActive(dto.getActive());
        refreshCatalog(product);
        products.saveAndFlush(product);
        return describedVariant(product,variantId);
    }

    private void validateUpdateIdentity(ProductVariant variant,ProductVariantDto dto) {
        if (Boolean.TRUE.equals(variant.getLegacy())) throw new BadRequestException("Biến thể lịch sử cần đối soát, không được sửa hoặc bật bán");
        if ((dto.isColorSupplied() || dto.getColor()!=null) && !Objects.equals(clean(dto.getColor()),clean(variant.getColor()))
                || (dto.isSizeSupplied() || dto.getSize()!=null) && !Objects.equals(clean(dto.getSize()),clean(variant.getSize()))
                || (dto.isWeightGripSupplied() || dto.getWeightGrip()!=null) && !Objects.equals(clean(dto.getWeightGrip()),clean(variant.getWeightGrip()))
                || (dto.isPackagingSupplied() || dto.getPackaging()!=null) && !Objects.equals(clean(dto.getPackaging()),clean(variant.getPackaging()))
                || dto.getSku()!=null && !Objects.equals(dto.getSku(),variant.getSku())
                || dto.getId()!=null && !Objects.equals(dto.getId(),variant.getId())
                || dto.getReservedStock()!=null && !Objects.equals(dto.getReservedStock(),variant.getReservedStock())
                || Boolean.TRUE.equals(dto.getLegacy()))
            throw new BadRequestException("Không sửa định danh tổ hợp. Hãy tắt biến thể cũ và thêm tổ hợp mới; giữ lịch sử đơn hàng");
    }

    private void validateActivation(Product product,ProductVariant variant) {
        var dto=ProductVariantDto.builder().color(variant.getColor()).size(variant.getSize())
                .weightGrip(variant.getWeightGrip()).packaging(variant.getPackaging()).build();
        validateAttributes(product,dto);
        var active=new ArrayList<>(activeVariants(product.getVariants()));
        if (!Boolean.TRUE.equals(variant.getActive())) active.add(variant);
        validateLength(summary(active,ProductVariant::getColor),200,"Tổng các lựa chọn màu sắc");
        Long category=product.getCategory()==null ? null : product.getCategory().getId();
        if (Objects.equals(category,1L)) validateLength(summary(active,ProductVariant::getWeightGrip),50,"Tổng các lựa chọn trọng lượng/cỡ cán");
        if (Objects.equals(category,5L)) validateLength(summary(active,ProductVariant::getPackaging),50,"Tổng các lựa chọn quy cách");
    }
}
