import http from "k6/http";
import { SERVICES } from "../utils/config.js";
// import { getToken } from "../utils/auth.js";
import { check } from "k6";
//35.64*0.7=24.9
export const options = {
    scenarios: {
        fixed_load: {
            executor: "constant-arrival-rate",
            rate: 24,           
            timeUnit: "1s",
            duration: "2m",
            preAllocatedVUs: 40,
            maxVUs: 250,
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
        `${SERVICES.customer}/signup`,
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