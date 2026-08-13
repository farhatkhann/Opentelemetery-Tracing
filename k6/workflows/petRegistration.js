import http from 'k6/http';
import { check, sleep } from 'k6';
import exec from 'k6/execution';

const BASE_URL = __ENV.BASE_URL || "http://localhost:8080";

// Set to true to deliberately hammer a single owner (hot-row contention test).
// Set to false (default) to spread load across owners like realistic traffic.
const HOT_ROW_MODE = __ENV.HOT_ROW_MODE === 'true';
const OWNER_ID_POOL = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]; // adjust to match seeded owner IDs
//15*0.7=10
export const options = {
    scenarios: {
        fixed_load: {
            executor: "constant-arrival-rate",
            rate: 10,           
            timeUnit: "1s",
            duration: "2m",
            preAllocatedVUs: 40,
            maxVUs: 500,
        },
    },
};
// export const options = {
//     scenarios: {
//         find_breaking_point: {
//             executor: "ramping-arrival-rate",
//             startRate: 5,
//             timeUnit: "1s",
//             preAllocatedVUs: 50,
//             maxVUs: 300,
//             stages: [
//                 { duration: "30s", target: 10 },
//                 { duration: "30s", target: 20 },
//                 { duration: "30s", target: 30 },
//                 // { duration: "30s", target: 40 },
//                 // { duration: "30s", target: 50 },
//                 // { duration: "30s", target: 60 },
//                 // { duration: "30s", target: 70 },
//                 // { duration: "30s", target: 80 },
//                 // { duration: "30s", target: 90 },
//                 // { duration: "30s", target: 100 },
//                 // { duration: "30s", target: 110 },
//                 // { duration: "30s", target: 120 },
//                 // { duration: "30s", target: 130 },
//             ]
//         },
//     },
// };
export default function () {

    const ownerId = HOT_ROW_MODE
        ? 1
        : OWNER_ID_POOL[Math.floor(Math.random() * OWNER_ID_POOL.length)];

    // Collision-proof name: unique per VU + iteration + timestamp.
    const uniqueName = `Dog_${exec.vu.idInTest}_${exec.vu.iterationInInstance}_${Date.now()}`;

    const payload = {
        name: uniqueName,
        birthDate: "2022-01-01",
        type: "dog"
    };

    const body = Object.entries(payload)
        .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
        .join('&');

    const params = {
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        redirects: 0 // don't auto-follow the 302, we want to see it
    };

    const res = http.post(
        `${BASE_URL}/owners/${ownerId}/pets/new`,
        body,
        params
    );

    const ok = check(res, {
        'Pet Added': r => r.status === 302
    });

    if (!ok) {
        console.log(`[Pet Add] ownerId=${ownerId} status=${res.status}`);
        console.log(`[Pet Add] body=${res.body ? res.body.substring(0, 300) : ''}`);
    }

    sleep(1);

}