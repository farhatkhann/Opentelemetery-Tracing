import http from "k6/http";
import { BASE_URL, PRODUCT_ID } from "../utils/config.js";
import { getToken } from "../utils/auth.js";

export default function () {
    const token = getToken();

    const params = {
        headers: {
            Authorization: `Bearer ${token}`
        }
    };

    const res = http.del(
        `${BASE_URL}/cart/${PRODUCT_ID}`,
        null,
        params
    );

    // console.log(
    //     `DeleteCart: ${res.status}, ${res.timings.duration} ms`
    // );
}