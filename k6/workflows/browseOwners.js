import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = "http://localhost:8080";
//149*0.7=104/34
export const options = {
    scenarios: {
        fixed_load: {
            executor: "constant-arrival-rate",
            rate: 34,             
            timeUnit: "1s",
            duration: "2m",
            preAllocatedVUs: 10,   
            maxVUs: 300,          
        },
    },
};

export default function () {

    let res = http.get(`${BASE_URL}/api/customer/owners?lastName=`);

    check(res, {
        'Owners loaded': (r) => r.status === 200,
    });

    res = http.get(`${BASE_URL}/api/customer/owners/1`);

    check(res, {
        'Owner details': (r) => r.status === 200,
    });

    res = http.get(`${BASE_URL}/api/vet/vets`);

    check(res, {
        'Veterinarians loaded': (r) => r.status === 200,
    });

    sleep(1);
}