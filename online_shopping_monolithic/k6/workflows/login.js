// import http from "k6/http";
// import { BASE_URL, USER } from "../utils/config.js";
// import { check } from "k6";
// export const options = {
//     vus: 8,
//     duration: '2m',
// };
// export default function () {
//     const payload = JSON.stringify({
//         email: USER.email,
//         password: USER.password
//     });

//     const params = {
//         headers: {
//             "Content-Type": "application/json"
//         }
//     };
//     const res = http.post(
//         `${BASE_URL}/customer/login`,
//         payload,
//         params
//     );
//     check(res, {
//         "login successful": (r) => r.status === 200,
//     });
//     if (res.status !== 200) {
//         throw new Error("Login failed");
//     }
//     return res.json("token");
// }


import http from "k6/http";
import { BASE_URL, USER } from "../utils/config.js";
import { check } from "k6";

export const options = {
    scenarios: {
        fixed_load: {
            executor: "constant-arrival-rate",
            rate: 39,              // target requests/sec ≈ 70% of saturation (55.93 req/s)
            timeUnit: "1s",
            duration: "2m",
            preAllocatedVUs: 10,   // starting pool of VUs k6 uses to hit the rate
            maxVUs: 20,            // ceiling if latency forces more VUs to sustain 39 req/s
        },
    },
};

export default function () {
    const payload = JSON.stringify({
        email: USER.email,
        password: USER.password
    });

    const params = {
        headers: {
            "Content-Type": "application/json"
        }
    };

    const res = http.post(
        `${BASE_URL}/customer/login`,
        payload,
        params
    );

    check(res, {
        "login successful": (r) => r.status === 200,
    });

    if (res.status !== 200) {
        throw new Error("Login failed");
    }
}