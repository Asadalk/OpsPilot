# Checkout Configuration Mismatch Postmortem

The checkout-api 500 spike followed a deployment that carried a different PAYMENT_GATEWAY_URL from the production baseline. The strongest evidence was the configuration mismatch log aligned with the deployment timestamp and increased 5xx rate.

The corrective procedure is to compare rendered configuration with the approved baseline, identify the configuration owner, and verify the next deployment in the simulator. Do not infer a code regression from a 500 spike until configuration and dependency evidence have been checked.
