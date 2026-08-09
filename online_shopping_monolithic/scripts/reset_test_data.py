"""
reset_test_data.py

Resets the test customer's accumulated data in MongoDB before each
experiment run.

Why this exists: customer_workflow.js calls POST /customer/address on
every k6 iteration. The backend (CreateAddress in customer-repository.js)
appends a new address document to the customer's `address` array on every
call and never cleans it up. Left unchecked, this array grows without
bound across repeated runs, which:
  - inflates .populate("address") queries into massive $in lookups
  - inflates OpenTelemetry span payloads (db.statement) to the point
    where the OTLP exporter times out and silently drops spans
  - makes response-time/throughput numbers drift upward run-over-run,
    contaminating any saturation pilot or fixed-load comparison

This script resets the address array to empty and deletes the now-orphaned
address documents, so every run starts from the same clean state.

Usage:
    python reset_test_data.py --email test@example.com
    python reset_test_data.py --email test@example.com --mongo-uri mongodb://127.0.0.1:27017/amazon_demo
"""

import argparse
import sys

try:
    from pymongo import MongoClient
except ImportError:
    print("❌ pymongo is not installed. Install it with:")
    print("   pip install pymongo")
    sys.exit(1)

parser = argparse.ArgumentParser(
    description="Reset accumulated test data for the k6 test customer"
)

parser.add_argument(
    "--email",
    required=True,
    help="Email of the test customer used by k6 scripts (USER.email in config.js)"
)

parser.add_argument(
    "--mongo-uri",
    default="mongodb://127.0.0.1:27017/amazon_demo",
    help="MongoDB connection string (default: mongodb://127.0.0.1:27017/amazon_demo)"
)

parser.add_argument(
    "--dry-run",
    action="store_true",
    help="Show what would be deleted/reset without making changes"
)

args = parser.parse_args()

print("=" * 60)
print("Resetting Test Data")
print("=" * 60)

client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=5000)

try:
    client.admin.command("ping")
except Exception as e:
    print(f"❌ Could not connect to MongoDB at {args.mongo_uri}")
    print(f"   {e}")
    sys.exit(1)

db = client.get_default_database()

customer = db.customers.find_one({"email": args.email})

if customer is None:
    print(f"⚠️  No customer found with email '{args.email}'. Nothing to reset.")
    sys.exit(0)

customer_id = customer["_id"]
address_ids = customer.get("address", [])

print(f"Customer         : {args.email}")
print(f"Customer _id     : {customer_id}")
print(f"Addresses linked : {len(address_ids)}")

if not address_ids:
    print("\n✅ Address array already empty. Nothing to do.")
    sys.exit(0)

if args.dry_run:
    print(f"\n[DRY RUN] Would delete {len(address_ids)} address document(s) "
          f"and reset customer.address to [].")
    sys.exit(0)

# Delete the now-orphaned address documents themselves, not just the
# references on the customer, so the "addresses" collection doesn't
# grow unbounded across runs either.
delete_result = db.addresses.delete_many({"_id": {"$in": address_ids}})

update_result = db.customers.update_one(
    {"_id": customer_id},
    {"$set": {"address": []}}
)

print(f"\nDeleted address documents : {delete_result.deleted_count}")
print(f"Customer address array    : reset to [] "
      f"({'ok' if update_result.modified_count == 1 else 'no change made'})")

print("\n✅ Test data reset complete.")
