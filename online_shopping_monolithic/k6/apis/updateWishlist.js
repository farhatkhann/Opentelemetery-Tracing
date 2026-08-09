import http from "k6/http";
import { check } from "k6";
import { BASE_URL, PRODUCT_ID } from "../utils/config.js";
import { getToken } from "../utils/auth.js";

export default function () {
    const token = getToken();

    const payload = JSON.stringify({
        productId: PRODUCT_ID
    });

    const params = {
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
        }
    };

    const res = http.put(
        `${BASE_URL}/wishlist`,
        payload,
        params
    );

    // console.log(
    //     `UpdateWishlist: ${res.status}, ${res.timings.duration} ms`
    // );

    // check(res, {
    //     "Wishlist updated successfully": (r) => r.status === 200,
    // });
}

//plato