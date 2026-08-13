import http from 'k6/http';
// import { BASE_URL } from '../utils/config';
import { check, sleep } from 'k6';
const BASE_URL = "http://localhost:8080";
//148*0.7=103/3=34
export const options = {
    scenarios: {
        fixed_load: {
            executor: "constant-arrival-rate",
            rate: 34,           
            timeUnit: "1s",
            duration: "2m",
            preAllocatedVUs: 40,
            maxVUs: 300,
        },
    },
};
export default function () {

    let res = http.get(`${BASE_URL}/owners?lastName=`);

    check(res, {
        'Owners loaded': (r) => r.status === 200,
    });

    res = http.get(`${BASE_URL}/owners/1`);

    check(res, {
        'Owner details': (r) => r.status === 200,
    });

    res = http.get(`${BASE_URL}/vets`);

    check(res, {
        'Veterinarians loaded': (r) => r.status === 200,
    });

    sleep(1);
}