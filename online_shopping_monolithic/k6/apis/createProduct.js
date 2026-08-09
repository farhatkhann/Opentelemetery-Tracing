import http from "k6/http";
import { BASE_URL } from "../utils/config.js";
import { getToken } from "../utils/auth.js";

export default function () {

    const payload = JSON.stringify({
        name: `Product_${__VU}_${__ITER}`,
        desc: "Performance Testing Product",
        type: "Electronics",
        unit: 10,
        price: 1000,
        available: true,
        suplier: "ABC Supplier",
        banner: "banner.jpg"
    });

    const params = {
        headers: {
            "Content-Type": "application/json"
        }
    };

    const res = http.post(
        `${BASE_URL}/product/create`,
        payload,
        params
    );

    // console.log(
    //     `CreateProduct: ${res.status}, ${res.timings.duration} ms`
    // );
}