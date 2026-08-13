import http from 'k6/http';
import { check, sleep } from 'k6';
// import { BASE_URL } from '../utils/config.js';
const BASE_URL = "http://localhost:8080";
//100*0.7=70/3=23
export const options = {
    scenarios: {
        fixed_load: {
            executor: "constant-arrival-rate",
            rate: 15,           
            timeUnit: "1s",
            duration: "2m",
            preAllocatedVUs: 40,
            maxVUs: 300,
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
//                 { duration: "30s", target: 40 },
//                 { duration: "30s", target: 50 },
//                 { duration: "30s", target: 60 },
//                 { duration: "30s", target: 70 },
//                 { duration: "30s", target: 80 },
//                 { duration: "30s", target: 90 },
//                 { duration: "30s", target: 100 },
//                 { duration: "30s", target: 110 },
//                 { duration: "30s", target: 120 },
//                 { duration: "30s", target: 130 },
//             ]
//         },
//     },
// };
export default function () {

    let res = http.get(`${BASE_URL}/owners?lastName=`);

    check(res, {
        'Search Owners': r => r.status === 200
    });

    res = http.get(`${BASE_URL}/owners/1`);

    check(res, {
        'View Owner': r => r.status === 200
    });

    res = http.get(`${BASE_URL}/vets`);

    check(res, {
        'View Vets': r => r.status === 200
    });

    sleep(1);

}