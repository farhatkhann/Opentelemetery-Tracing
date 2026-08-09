import http from "k6/http";
import { BASE_URL } from "../utils/config.js";
// import { getToken } from "../utils/auth.js";
import { check } from "k6";
export const options = {
    scenarios: {
        fixed_load: {
            executor: "constant-arrival-rate",
            rate: 39,              // target requests/sec ≈ 70% of saturation (55.93 req/s)
            timeUnit: "1s",
            duration: "2m",
            preAllocatedVUs: 20,   // starting pool of VUs k6 uses to hit the rate
            maxVUs: 60,            // ceiling if latency forces more VUs to sustain 39 req/s
        },
    },
};
export default function () {
    const email = `test${Date.now()}@test.com`;
    // const email = `user_${__VU}_${__ITER}@test.com`;

    const signupPayload = JSON.stringify({
        email,
        password: "123456",
        phone: "9876543210"
    });

    const params = {
        headers: {
            "Content-Type": "application/json"
        }
    };

    const res = http.post(
        `${BASE_URL}/customer/signup`,
        signupPayload,
        params
    );

    check(res, {
        "Signup successful": (r) => r.status === 200,
    });

    if (res.status !== 200) {
        throw new Error("Signup failed");
    }

    // console.log(
    //     `Signup: ${signupRes.status}, ${signupRes.timings.duration} ms`
    // );

}

//Response time: http_req_duration
//k6 run --vus 20 --duration 30s test.js
// http_reqs: 6000
// Throughput = 6000 / 30 = 200 Requests/Second (RPS)