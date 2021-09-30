-- Add a 10ms delay to each message, possibly this compares better to powerful hardware in latency!
-- Random with return math.random(10, 50)
--function delay()
--    return 10
--end

-- example reporting script which demonstrates a custom
-- done() function that prints latency percentiles as CSV

done = function(summary, latency, requests)
    io.write("LATENCY\n")
    io.write("MAX,", latency.max)
    io.write("\nMIN,", latency.min)
    io.write("\nMEAN,", latency.mean)
    io.write("\nSTDEV,", latency.stdev)
    io.write("\n")
    for _, p in pairs({ 50, 90, 99, 99.999 }) do
        n = latency:percentile(p)
        io.write(string.format("%g%%,%d\n", p, n))
    end
    io.write("SUMMARY\n")
    io.write("DURATION,", summary.duration, "\n")
    io.write("REQUESTS,", summary.requests, "\n")
    io.write("BYTES,", summary.bytes, "\n")
    io.write("CONNERR,", summary.errors.connect, "\n")
    io.write("READERR,", summary.errors.read, "\n")
    io.write("WRITERR,", summary.errors.write, "\n")
    io.write("STATERR,", summary.errors.status, "\n")
    io.write("TIMEOUT,", summary.errors.timeout, "\n")
end
