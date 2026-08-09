import http from "k6/http";
import { BASE_URL } from "../utils/config.js";
import { getToken } from "../utils/auth.js";

export default function () {

    const res = http.get(
        `${BASE_URL}/category/Electronics`
    );

    // console.log(
    //     `GetCategory: ${res.status}, ${res.timings.duration} ms`
    // );
}