// export const BASE_URL = "http://localhost:8001";
// export const PRODUCT_ID = "6a59eacd2a0a4a53f47fa171";
// export const QUANTITY = 2;
// export const TAX_NUMBER = "abc123";
// export const USER = {
//     email: "farhat@gmail.com",
//     password: "123456"
// };

// k6/config.js
//
// Single source of truth for service base URLs used across all k6
// workflow scripts. Add an entry here whenever a new service comes
// online, then import { SERVICES } wherever you need it.
//
// NOTE: keep the service keys here consistent with SERVICE_CONFIG in
// run_experiment.py (customer / products / shopping / ...). They're
// separate files (JS vs Python, different runtimes) so there's no way
// to share one literal config between them, but keeping the *names*
// aligned makes it easy to cross-reference when reading results.

export const SERVICES = {
  customer: 'http://localhost:8001',
  products: 'http://localhost:8002',
  shopping: 'http://localhost:8003',
};

// A pool of test users, one per (or shared round-robin across) virtual user.
// Add as many as the max VU count you plan to run so no two VUs ever share
// a wishlist/cart during a test.
export const USERS = [
    { email: "user1@gmail.com", password: "123456" },
    { email: "user2@gmail.com", password: "123456" },
    { email: "user3@gmail.com", password: "123456" },
    { email: "user4@gmail.com", password: "123456" },
    { email: "user5@gmail.com", password: "123456" },
    { email: "user6@gmail.com", password: "123456" },
    { email: "user7@gmail.com", password: "123456" },
    { email: "user8@gmail.com", password: "123456" },
    { email: "user9@gmail.com", password: "123456" },
    { email: "user10@gmail.com", password: "123456" },
];

// A pool of product IDs so add/delete operations for different VUs never
// collide on the same product, even if they somehow shared a wishlist.
export const PRODUCT_IDS = [
    "6a7082a9c8416b002067dfeb",
    "6a7082edc8416b002067dfed",
    "6a708324c8416b002067dfef",
    "6a708353c8416b002067dff1",
    "6a708387c8416b002067dff3",
];

export const QUANTITY = 2;
export const TAX_NUMBER = "tax123";

// Kept for backward compatibility / scripts that only need a single fixed
// user or product (not recommended for load tests with concurrency).
export const USER = USERS[0];
export const PRODUCT_ID = PRODUCT_IDS[0];