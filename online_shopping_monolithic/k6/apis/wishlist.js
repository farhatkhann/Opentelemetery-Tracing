import http from "k6/http";
import { BASE_URL } from "../utils/config.js";
import { getToken } from "../utils/auth.js";

export default function () {
    const token = getToken();

    const params = {
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
        }
    };

    const res = http.get(
        `${BASE_URL}/customer/wishlist`,
        params
    );

    //  console.log(
    //     `Wishlist: ${res.status}, ${res.timings.duration} ms`
    // );
}