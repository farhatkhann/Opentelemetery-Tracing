import http from "k6/http";
import { check } from "k6";
import { BASE_URL, PRODUCT_ID } from "../utils/config.js";
import { getToken } from "../utils/auth.js";

export default function () {
    const token = getToken();
    const params = {
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
        }
    };

    const res = http.del(
        `${BASE_URL}/wishlist/${PRODUCT_ID}`,
        null,
        params
    );

    // console.log(
    //     `DeleteWishlist: ${res.status}, ${res.timings.duration} ms`
    // );

    // check(res, {
    //     "Wishlist item deleted": (r) => r.status === 200,
    // });
}