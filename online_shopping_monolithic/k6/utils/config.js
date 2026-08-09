// export const BASE_URL = "http://localhost:8001";
// export const PRODUCT_ID = "6a59eacd2a0a4a53f47fa171";
// export const QUANTITY = 2;
// export const TAX_NUMBER = "abc123";
// export const USER = {
//     email: "farhat@gmail.com",
//     password: "123456"
// };

export const BASE_URL = "http://localhost:8001";

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
    "6a69b21ab69b012ff4d077ca",
    "6a69b243b69b012ff4d077cc",
    "6a69b27cb69b012ff4d077ce",
    "6a69b2b1b69b012ff4d077d0",
    "6a69b2edb69b012ff4d077d2",
];

export const QUANTITY = 2;
export const TAX_NUMBER = "tax123";

// Kept for backward compatibility / scripts that only need a single fixed
// user or product (not recommended for load tests with concurrency).
export const USER = USERS[0];
export const PRODUCT_ID = PRODUCT_IDS[0];