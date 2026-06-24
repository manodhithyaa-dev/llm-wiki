#!/bin/bash

# Activate virtual environment
source venv/bin/activate

queries=(
    "How to replace a motor"
    "Screwdriver"
    "Signal quality"
    "Fixing the running belt"
    "Setup mode instructions"
    "Error codes listing"
    "Clearing last error on treadmill"
    "MCB error"
    "CMSO phone number"
    "DCS 5000 power cable"
    "Putting together the DVR rack"
    "How do I pay with my phone"
    "Cancel an appointment"
    "Wiring diagram for motor"
    "Software license"
    "Membership discount"
    "Tools"
    "MPE"
    "PayTM"
    "Warranty"
)

echo "========================================="
echo "Running 20 Ambiguity Test Queries"
echo "========================================="

for query in "${queries[@]}"
do
    echo
    echo "=================================================="
    echo "QUERY: $query"
    echo "=================================================="

    python3 main.py query "$query"

    echo
    echo "--------------------------------------------------"
    echo
done

echo "========================================="
echo "All tests completed"
echo "========================================="
