import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = "http://localhost:8080";
//60*0.7=42/2=21
export const options = {
    scenarios: {
        fixed_load: {
            executor: "constant-arrival-rate",
            rate: 42,             
            timeUnit: "1s",
            duration: "2m",
            preAllocatedVUs: 10,   
            maxVUs: 800,          
        },
    },
};

export default function () {

    const ownerId = 1;

    // Pet creation requires a real petType id from the customers-service
    // catalog (not a made-up string like the monolith's "dog"), so fetch
    // it first rather than hardcoding — the seed data's ids can vary.
    const typesRes = http.get(`${BASE_URL}/api/customer/petTypes`);

    check(typesRes, {
        'Pet types loaded': (r) => r.status === 200,
    });

    let typeId = 1;
    try {
        const types = typesRes.json();
        if (Array.isArray(types) && types.length > 0) {
            typeId = types[0].id;
        }
    } catch (e) {
        // fall back to typeId 1 if parsing fails
    }

    const payload = JSON.stringify({
        name: "Dog" + Math.floor(Math.random() * 10000),
        birthDate: "2022-01-01",
        typeId: typeId
    });

    const params = {
        headers: {
            'Content-Type': 'application/json'
        }
    };

    const res = http.post(
        `${BASE_URL}/api/customer/owners/${ownerId}/pets`,
        payload,
        params
    );

    check(res, {
        'Pet Added': (r) => r.status === 201,
    });

    sleep(1);
}