import http from "k6/http";
import { BASE_URL, TAX_NUMBER, PRODUCT_ID, QUANTITY } from "../utils/config.js";
import { getToken } from "../utils/auth.js";

export default function () {
    const token = getToken();
    const params = {
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
        }
    };

    const payloadCart = JSON.stringify({
            productId: PRODUCT_ID,
            qty: QUANTITY
        });
    
        const resCart = http.put(
            `${BASE_URL}/cart`,
            payloadCart,
            params
        );

    const payloadOrder = JSON.stringify({
        txnNumber: TAX_NUMBER
    });

    const res = http.post(
        `${BASE_URL}/shopping/order`,
        payloadOrder,
        params
    );

    // console.log(
    //     `PlaceOrder: ${res.status}, ${res.timings.duration} ms`
    // );
}