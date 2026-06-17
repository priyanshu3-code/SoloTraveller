import os
from langsmith import Client

# Initialize client
client = Client()

# Get or create dataset
dataset_name = "solotraveller-evaluation-dataset"
print(f"Loading dataset: {dataset_name}")

# Try to get existing dataset first
existing_datasets = list(client.list_datasets(dataset_name=dataset_name))
if existing_datasets:
    dataset = existing_datasets[0]
    print(f"✅ Using existing dataset: {dataset.id}")
    print(f"   Current examples: {dataset.example_count}")
else:
    dataset = client.create_dataset(dataset_name=dataset_name)
    print(f"✅ Dataset created: {dataset.id}")

# Define test examples
test_examples = [
    {
        "inputs": {"situation": "A stranger approached me in Delhi offering authentic rubies at 50000 INR each. He said it's normally 200000 INR but gave me special pricing. He wants payment today only."},
        "outputs": {
            "expected_risk_level": "high",
            "expected_currency": "INR",
            "expected_location": "Delhi",
            "expected_prices": [50000, 200000],
            "expected_price_assessment": "inflated"
        }
    },
    {
        "inputs": {"situation": "I'm booking a hotel in London for 3 nights. The rate is 80 GBP per night, which is reasonable for a 4-star hotel. The booking goes through Booking.com with proper confirmation."},
        "outputs": {
            "expected_risk_level": "low",
            "expected_currency": "GBP",
            "expected_location": "London",
            "expected_prices": [80],
            "expected_price_assessment": "fair"
        }
    },
    {
        "inputs": {"situation": "A tuk-tuk driver in Bangkok quoted 2000 baht for a short ride. Normal fare for this distance is 50-100 baht. He wants cash payment immediately."},
        "outputs": {
            "expected_risk_level": "high",
            "expected_currency": "THB",
            "expected_location": "Bangkok",
            "expected_prices": [2000],
            "expected_price_assessment": "inflated"
        }
    },
    {
        "inputs": {"situation": "Booked a 5-day organized tour in Thailand for 15000 THB with a reputable tour operator. Includes accommodation, meals, and guided tours. Price is market rate."},
        "outputs": {
            "expected_risk_level": "low",
            "expected_currency": "THB",
            "expected_location": "Bangkok",
            "expected_prices": [15000],
            "expected_price_assessment": "fair"
        }
    },
    {
        "inputs": {"situation": "Found tickets to a sold-out concert in Paris on a sketchy site. Front row seats for only €80 EUR (original price was €450). Seller wants payment via untraceable gift cards. Very urgent—event is in 2 days."},
        "outputs": {
            "expected_risk_level": "high",
            "expected_currency": "EUR",
            "expected_location": "Paris",
            "expected_prices": [80, 450],
            "expected_price_assessment": "inflated"
        }
    },
]

# Upload examples
print(f"\n📤 Uploading {len(test_examples)} test examples...")
for i, example in enumerate(test_examples, 1):
    client.create_example(
        inputs=example["inputs"],
        outputs=example["outputs"],
        dataset_id=dataset.id
    )
    print(f"  ✅ Example {i}/5 uploaded")

print(f"\n✅ Dataset ready: {dataset_name}")
print(f"🔗 View in LangSmith: https://smith.langchain.com/datasets")
