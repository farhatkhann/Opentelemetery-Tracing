import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = "http://localhost:8080";
//60*0.7=42/4=10
export const options = {
    scenarios: {
        fixed_load: {
            executor: "constant-arrival-rate",
            rate: 5,             
            timeUnit: "1s",
            duration: "2m",
            preAllocatedVUs: 10,   
            maxVUs: 800,          
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
//                 { duration: "30s", target: 20 },
//                 { duration: "30s", target: 40 },
//                 { duration: "30s", target: 60 },
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

    let res = http.get(`${BASE_URL}/api/customer/owners?lastName=`);

    check(res, {
        'Search Owners': (r) => r.status === 200,
    });

    res = http.get(`${BASE_URL}/api/customer/owners/1`);

    check(res, {
        'View Owner': (r) => r.status === 200,
    });

    res = http.get(`${BASE_URL}/api/vet/vets`);

    check(res, {
        'View Vets': (r) => r.status === 200,
    });

    res = http.get(`${BASE_URL}/api/visit/owners/1/pets/1/visits`);

    check(res, {
        'View Visits': (r) => r.status === 200,
    });

    sleep(1);
}