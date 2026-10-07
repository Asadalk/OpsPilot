# Checkout Configuration Mismatch Postmortem

The checkout-api 500 spike for incident PAY-451 followed deployment v3.8.2, which carried a different PAYMENT_GATEWAY_URL from the production baseline. The strongest evidence was the CONFIG_MISMATCH log aligned with the deployment timestamp and increased 5xx rate.

The corrective procedure is to compare rendered configuration with the approved baseline, identify the configuration owner, and verify the next deployment in the simulator. Do not infer a code regression from a 500 spike until configuration and dependency evidence have been checked.
