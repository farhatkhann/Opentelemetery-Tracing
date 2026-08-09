import http from "k6/http";
import { BASE_URL, PRODUCT_ID, QUANTITY } from "../utils/config.js";
import { getToken } from "../utils/auth.js";

export default function () {
    const token = getToken();

    const payload = JSON.stringify({
        productId: PRODUCT_ID,
        qty: QUANTITY
    });

    const params = {
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`
        }
    };

    const res = http.put(
        `${BASE_URL}/cart`,
        payload,
        params
    );

    // console.log(
    //     `UpdateCart: ${res.status}, ${res.timings.duration} ms`
    // );
}