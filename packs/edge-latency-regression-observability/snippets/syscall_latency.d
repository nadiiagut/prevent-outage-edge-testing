#!/usr/sbin/dtrace -s
/*
 * syscall_latency.d - Measure syscall latencies by type
 * 
 * PRIVILEGED: Requires root or dtrace group membership
 * 
 * Usage:
 *   sudo dtrace -s syscall_latency.d -p <PID>
 *   sudo dtrace -s syscall_latency.d -c "command"
 *
 * Output: Histogram of latencies per syscall in nanoseconds
 */

#pragma D option quiet

dtrace:::BEGIN
{
    printf("Tracing syscalls... Hit Ctrl-C to stop.\n");
    start = timestamp;
}

syscall:::entry
/pid == $target || progenyof($target)/
{
    self->ts = timestamp;
    self->syscall = probefunc;
}

syscall:::return
/self->ts/
{
    @latency[self->syscall] = quantize(timestamp - self->ts);
    @count[self->syscall] = count();
    @total_ns[self->syscall] = sum(timestamp - self->ts);
    self->ts = 0;
    self->syscall = 0;
}

dtrace:::END
{
    printf("\n=== Syscall Latency Distribution (ns) ===\n");
    printa(@latency);
    
    printf("\n=== Syscall Counts ===\n");
    printa("%-20s %@d\n", @count);
    
    printf("\n=== Total Time per Syscall (ns) ===\n");
    printa("%-20s %@d\n", @total_ns);
    
    printf("\nTrace duration: %d ms\n", (timestamp - start) / 1000000);
}
