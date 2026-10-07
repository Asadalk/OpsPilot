# Payments Dependency Boundary

payments-api owns request handling for payment records but depends on a database connection pool. Latency can increase before the service becomes failed. Database timeout logs and high request-latency metrics together are stronger evidence than either signal alone.

The simulator separates service facts from dependency evidence. Use the service id and trace id to correlate records, and keep operational knowledge as supporting context rather than replacing observed runtime data.
