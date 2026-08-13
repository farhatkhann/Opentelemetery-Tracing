import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || "http://localhost:8080";

// Set to true to deliberately hammer a single pet (hot-row contention test).
// Set to false (default) to spread load across pets like realistic traffic.
const HOT_ROW_MODE = __ENV.HOT_ROW_MODE === 'true';

// Verified against PetClinic's seeded data.sql: (petId -> ownerId)
// pet 1->1, 2->2, 3->3, 4->3, 5->4, 6->5, 7->6, 8->6, 9->7, 10->8, 11->9, 12->10, 13->10
const OWNER_PET_POOL = [
    { ownerId: 1, petId: 1 },
    { ownerId: 2, petId: 2 },
    { ownerId: 3, petId: 3 },
    { ownerId: 3, petId: 4 },
    { ownerId: 4, petId: 5 },
    { ownerId: 5, petId: 6 },
    { ownerId: 6, petId: 7 },
    { ownerId: 6, petId: 8 },
    { ownerId: 7, petId: 9 },
    { ownerId: 8, petId: 10 },
    { ownerId: 9, petId: 11 },
    { ownerId: 10, petId: 12 },
    { ownerId: 10, petId: 13 },
];
//15*0.7=10
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
export const options = {
    scenarios: {
        fixed_load: {
            executor: "constant-arrival-rate",
            rate: 10,           
            timeUnit: "1s",
            duration: "2m",
            preAllocatedVUs: 40,
            maxVUs: 400,
        },
    },
};
function futureDateString(daysAhead) {
    const d = new Date();
    d.setDate(d.getDate() + daysAhead);
    return d.toISOString().split('T')[0]; // yyyy-MM-dd
}

export default function () {

    const target = HOT_ROW_MODE
        ? OWNER_PET_POOL[0]
        : OWNER_PET_POOL[Math.floor(Math.random() * OWNER_PET_POOL.length)];

    const ownerId = target.ownerId;
    const petId = target.petId;

    const payload = {
        date: futureDateString(7),
        description: "Regular Checkup"
    };

    const body = Object.entries(payload)
        .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
        .join('&');

    const params = {
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        redirects: 0
    };

    const res = http.post(
        `${BASE_URL}/owners/${ownerId}/pets/${petId}/visits/new`,
        body,
        params
    );

    const ok = check(res, {
        'Visit Added': r => r.status === 302
    });

    if (!ok) {
        console.log(`[Visit Add] ownerId=${ownerId} petId=${petId} status=${res.status}`);
        console.log(`[Visit Add] body=${res.body ? res.body.substring(0, 300) : ''}`);
    }

    sleep(1);

}