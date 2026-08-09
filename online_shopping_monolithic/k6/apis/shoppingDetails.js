import http from "k6/http";
import { BASE_URL } from "../utils/config.js";
import { getToken } from "../utils/auth.js";

export default function () {
    const token = getToken();
    const params = {
        headers: {
            Authorization: `Bearer ${token}`
        }
    };

    const res = http.get(
        `${BASE_URL}/customer/shoping-details`,
        params
    );

    //  console.log(
    //     `ShoppingDetails: ${res.status}, ${res.timings.duration} ms`
    // );
}