import http from "k6/http";
import { BASE_URL, PRODUCT_ID } from "../utils/config.js";
import { getToken } from "../utils/auth.js";

export default function () {

    const res = http.get(
        `${BASE_URL}/${PRODUCT_ID}`
    );

    // console.log(
    //     `GetDescription: ${res.status}, ${res.timings.duration} ms`
    // );
}