package com.sports.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Size;
import lombok.*;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class OrderItemRequest {
    @com.fasterxml.jackson.annotation.JsonSetter("quantity")
    public void readQuantity(java.math.BigDecimal value) {
        this.quantity = value == null ? null : value.intValueExact();
    }

    @com.fasterxml.jackson.annotation.JsonSetter("productId")
    public void readProductId(java.math.BigDecimal value) {
        this.productId = value == null ? null : value.longValueExact();
    }

    public OrderItemRequest(Long productId, Integer quantity) {
        this.productId = productId;
        this.quantity = quantity;
    }

    @NotNull(message = "ID sản phẩm không được để trống")
    @Positive
    private Long productId;
    @Positive private Long variantId;

    @NotNull(message = "Số lượng không được để trống")
    @Min(value = 1, message = "Số lượng phải lớn hơn hoặc bằng 1")
    @Max(100)
    private Integer quantity;

    @Size(max = 50)
    private String selectedSize;
    @Size(max = 200)
    private String selectedColor;
    @Size(max = 50)
    private String selectedWeight;
    @Size(max = 100)
    private String stringingService;
    @Size(max = 50)
    private String stringTension;
}
