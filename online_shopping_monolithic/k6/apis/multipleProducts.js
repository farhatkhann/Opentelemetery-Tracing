import http from "k6/http";
import { BASE_URL } from "../utils/config.js";
import { getToken } from "../utils/auth.js";

export default function () {

    const payload = JSON.stringify({
        ids: [
            "6a59eacd2a0a4a53f47fa171",
            "6a59eae12a0a4a53f47fa173"
        ]
    });

    const params = {
        headers: {
            "Content-Type": "application/json"
        }
    };

    const res = http.post(
        `${BASE_URL}/ids`,
        payload,
        params
    );

    // console.log(
    //     `getMultipleProducts: ${res.status}, ${res.timings.duration} ms`
    // );
}