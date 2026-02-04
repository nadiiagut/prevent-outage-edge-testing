/*
 * fault_inject.c - LD_PRELOAD library for fault injection
 * 
 * Compile:
 *   Linux:   gcc -shared -fPIC -o libfaultinject.so fault_inject.c -ldl -lpthread
 *   macOS:   gcc -dynamiclib -o libfaultinject.dylib fault_inject.c -lpthread
 *   FreeBSD: cc -shared -fPIC -o libfaultinject.so fault_inject.c -lpthread
 * 
 * Usage:
 *   FAULT_INJECT_ENABLED=1 FAULT_CONNECT_FAIL_RATE=0.1 \
 *   LD_PRELOAD=./libfaultinject.so ./myapp
 * 
 * Environment variables:
 *   FAULT_INJECT_ENABLED     - Enable injection (1/0)
 *   FAULT_CONNECT_FAIL_RATE  - Probability of connect() failure (0.0-1.0)
 *   FAULT_CONNECT_ERRNO      - errno for connect failures (e.g., ETIMEDOUT)
 *   FAULT_SEND_FAIL_RATE     - Probability of send()/write() failure
 *   FAULT_SEND_ERRNO         - errno for send failures (e.g., EPIPE)
 *   FAULT_RECV_FAIL_RATE     - Probability of recv()/read() failure
 *   FAULT_RECV_SHORT_RATE    - Probability of short read (partial data)
 *   FAULT_RECV_ERRNO         - errno for recv failures (e.g., ECONNRESET)
 *   FAULT_OPEN_FAIL_RATE     - Probability of open() failure
 *   FAULT_OPEN_ERRNO         - errno for open failures (e.g., ENOENT)
 *   FAULT_LATENCY_MS         - Added latency in milliseconds
 *   FAULT_TARGET_PORT        - Only affect connections to this port
 *   FAULT_LOG_FILE           - Log injected faults to this file
 */

#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <pthread.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

/* Configuration from environment */
static int g_enabled = 0;
static double g_connect_fail_rate = 0.0;
static int g_connect_errno = ETIMEDOUT;
static double g_send_fail_rate = 0.0;
static int g_send_errno = EPIPE;
static double g_recv_fail_rate = 0.0;
static double g_recv_short_rate = 0.0;
static int g_recv_errno = ECONNRESET;
static double g_open_fail_rate = 0.0;
static int g_open_errno = ENOENT;
static int g_latency_ms = 0;
static int g_target_port = 0;
static FILE *g_log_file = NULL;
static pthread_mutex_t g_mutex = PTHREAD_MUTEX_INITIALIZER;
static int g_initialized = 0;

/* Statistics */
static unsigned long g_stat_connect_injected = 0;
static unsigned long g_stat_send_injected = 0;
static unsigned long g_stat_recv_injected = 0;
static unsigned long g_stat_short_reads = 0;

/* Original function pointers */
static int (*real_connect)(int, const struct sockaddr *, socklen_t) = NULL;
static ssize_t (*real_send)(int, const void *, size_t, int) = NULL;
static ssize_t (*real_recv)(int, void *, size_t, int) = NULL;
static ssize_t (*real_write)(int, const void *, size_t) = NULL;
static ssize_t (*real_read)(int, void *, size_t) = NULL;
static int (*real_open)(const char *, int, ...) = NULL;
static int (*real_close)(int) = NULL;

/* Track which fds are targeted sockets */
#define MAX_TRACKED_FDS 4096
static int g_targeted_fds[MAX_TRACKED_FDS] = {0};

/* Parse errno name to value */
static int parse_errno(const char *name) {
    if (!name) return 0;
    if (strcmp(name, "EPIPE") == 0) return EPIPE;
    if (strcmp(name, "ECONNRESET") == 0) return ECONNRESET;
    if (strcmp(name, "ECONNREFUSED") == 0) return ECONNREFUSED;
    if (strcmp(name, "ETIMEDOUT") == 0) return ETIMEDOUT;
#ifdef ENETUNREACH
    if (strcmp(name, "ENETUNREACH") == 0) return ENETUNREACH;
#endif
#ifdef EHOSTUNREACH
    if (strcmp(name, "EHOSTUNREACH") == 0) return EHOSTUNREACH;
#endif
    if (strcmp(name, "ENOENT") == 0) return ENOENT;
    if (strcmp(name, "EACCES") == 0) return EACCES;
    if (strcmp(name, "EIO") == 0) return EIO;
    if (strcmp(name, "ENOSPC") == 0) return ENOSPC;
    if (strcmp(name, "EROFS") == 0) return EROFS;
    return atoi(name);
}

/* Get errno name for logging */
static const char *errno_name(int err) {
    switch (err) {
        case EPIPE: return "EPIPE";
        case ECONNRESET: return "ECONNRESET";
        case ECONNREFUSED: return "ECONNREFUSED";
        case ETIMEDOUT: return "ETIMEDOUT";
        case ENOENT: return "ENOENT";
        case EACCES: return "EACCES";
        case EIO: return "EIO";
        default: return "?";
    }
}

/* Initialize from environment */
static void init_config(void) {
    if (g_initialized) return;
    pthread_mutex_lock(&g_mutex);
    if (g_initialized) {
        pthread_mutex_unlock(&g_mutex);
        return;
    }
    
    const char *val;
    
    val = getenv("FAULT_INJECT_ENABLED");
    g_enabled = val && (strcmp(val, "1") == 0 || strcmp(val, "true") == 0);
    
    val = getenv("FAULT_CONNECT_FAIL_RATE");
    if (val) g_connect_fail_rate = atof(val);
    
    val = getenv("FAULT_CONNECT_ERRNO");
    if (val) g_connect_errno = parse_errno(val);
    
    val = getenv("FAULT_SEND_FAIL_RATE");
    if (val) g_send_fail_rate = atof(val);
    
    val = getenv("FAULT_SEND_ERRNO");
    if (val) g_send_errno = parse_errno(val);
    
    val = getenv("FAULT_RECV_FAIL_RATE");
    if (val) g_recv_fail_rate = atof(val);
    
    val = getenv("FAULT_RECV_SHORT_RATE");
    if (val) g_recv_short_rate = atof(val);
    
    val = getenv("FAULT_RECV_ERRNO");
    if (val) g_recv_errno = parse_errno(val);
    
    val = getenv("FAULT_OPEN_FAIL_RATE");
    if (val) g_open_fail_rate = atof(val);
    
    val = getenv("FAULT_OPEN_ERRNO");
    if (val) g_open_errno = parse_errno(val);
    
    val = getenv("FAULT_LATENCY_MS");
    if (val) g_latency_ms = atoi(val);
    
    val = getenv("FAULT_TARGET_PORT");
    if (val) g_target_port = atoi(val);
    
    val = getenv("FAULT_LOG_FILE");
    if (val) {
        g_log_file = fopen(val, "a");
        if (g_log_file) {
            setbuf(g_log_file, NULL);  /* Unbuffered */
        }
    }
    
    /* Seed random with high-resolution time */
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    srand((unsigned)(ts.tv_sec ^ ts.tv_nsec ^ getpid()));
    
    /* Load real functions */
    real_connect = dlsym(RTLD_NEXT, "connect");
    real_send = dlsym(RTLD_NEXT, "send");
    real_recv = dlsym(RTLD_NEXT, "recv");
    real_write = dlsym(RTLD_NEXT, "write");
    real_read = dlsym(RTLD_NEXT, "read");
    real_open = dlsym(RTLD_NEXT, "open");
    real_close = dlsym(RTLD_NEXT, "close");
    
    memset(g_targeted_fds, 0, sizeof(g_targeted_fds));
    
    g_initialized = 1;
    
    if (g_log_file && g_enabled) {
        fprintf(g_log_file, "[INIT] libfaultinject loaded (pid=%d)\n", getpid());
        fprintf(g_log_file, "[INIT] connect_fail_rate=%.2f errno=%s\n", 
                g_connect_fail_rate, errno_name(g_connect_errno));
        fprintf(g_log_file, "[INIT] send_fail_rate=%.2f errno=%s\n",
                g_send_fail_rate, errno_name(g_send_errno));
        fprintf(g_log_file, "[INIT] recv_fail_rate=%.2f recv_short_rate=%.2f errno=%s\n",
                g_recv_fail_rate, g_recv_short_rate, errno_name(g_recv_errno));
        if (g_target_port) {
            fprintf(g_log_file, "[INIT] targeting port %d only\n", g_target_port);
        }
    }
    
    pthread_mutex_unlock(&g_mutex);
}

/* Check if should inject fault based on rate */
static int should_inject(double rate) {
    if (rate <= 0.0) return 0;
    if (rate >= 1.0) return 1;
    return ((double)rand() / RAND_MAX) < rate;
}

/* Log injection event */
static void log_inject(const char *func, int fd, const char *detail) {
    if (!g_log_file) return;
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    fprintf(g_log_file, "[%ld.%03ld] INJECT %s (fd=%d) %s\n",
            (long)ts.tv_sec, ts.tv_nsec / 1000000, func, fd, detail);
}

/* Add latency if configured */
static void add_latency(void) {
    if (g_latency_ms > 0) {
        struct timespec ts = {
            .tv_sec = g_latency_ms / 1000,
            .tv_nsec = (g_latency_ms % 1000) * 1000000
        };
        nanosleep(&ts, NULL);
    }
}

/* Check if fd is a targeted socket */
static int is_targeted_fd(int fd) {
    if (fd < 0 || fd >= MAX_TRACKED_FDS) return 0;
    return g_targeted_fds[fd];
}

/* Mark fd as targeted */
static void mark_targeted_fd(int fd) {
    if (fd >= 0 && fd < MAX_TRACKED_FDS) {
        g_targeted_fds[fd] = 1;
    }
}

/* Unmark fd */
static void unmark_targeted_fd(int fd) {
    if (fd >= 0 && fd < MAX_TRACKED_FDS) {
        g_targeted_fds[fd] = 0;
    }
}

/* Check if address matches target port */
static int matches_target(const struct sockaddr *addr) {
    if (g_target_port == 0) return 1;  /* No filter */
    
    if (addr->sa_family == AF_INET) {
        const struct sockaddr_in *sin = (const struct sockaddr_in *)addr;
        return ntohs(sin->sin_port) == g_target_port;
    } else if (addr->sa_family == AF_INET6) {
        const struct sockaddr_in6 *sin6 = (const struct sockaddr_in6 *)addr;
        return ntohs(sin6->sin6_port) == g_target_port;
    }
    return 0;
}

/* Intercepted connect() */
int connect(int sockfd, const struct sockaddr *addr, socklen_t addrlen) {
    init_config();
    
    if (!g_enabled || !real_connect) {
        return real_connect ? real_connect(sockfd, addr, addrlen) : -1;
    }
    
    int targeted = matches_target(addr);
    if (targeted) {
        mark_targeted_fd(sockfd);
    }
    
    add_latency();
    
    if (targeted && should_inject(g_connect_fail_rate)) {
        char detail[256];
        char addr_str[INET6_ADDRSTRLEN] = "?";
        int port = 0;
        
        if (addr->sa_family == AF_INET) {
            const struct sockaddr_in *sin = (const struct sockaddr_in *)addr;
            inet_ntop(AF_INET, &sin->sin_addr, addr_str, sizeof(addr_str));
            port = ntohs(sin->sin_port);
        } else if (addr->sa_family == AF_INET6) {
            const struct sockaddr_in6 *sin6 = (const struct sockaddr_in6 *)addr;
            inet_ntop(AF_INET6, &sin6->sin6_addr, addr_str, sizeof(addr_str));
            port = ntohs(sin6->sin6_port);
        }
        
        snprintf(detail, sizeof(detail), "-> %s (addr=%s:%d)", 
                 errno_name(g_connect_errno), addr_str, port);
        log_inject("connect", sockfd, detail);
        
        g_stat_connect_injected++;
        errno = g_connect_errno;
        return -1;
    }
    
    return real_connect(sockfd, addr, addrlen);
}

/* Intercepted send() */
ssize_t send(int sockfd, const void *buf, size_t len, int flags) {
    init_config();
    
    if (!g_enabled || !real_send) {
        return real_send ? real_send(sockfd, buf, len, flags) : -1;
    }
    
    if (!is_targeted_fd(sockfd) && g_target_port != 0) {
        return real_send(sockfd, buf, len, flags);
    }
    
    add_latency();
    
    if (should_inject(g_send_fail_rate)) {
        char detail[128];
        snprintf(detail, sizeof(detail), "-> %s (len=%zu)", 
                 errno_name(g_send_errno), len);
        log_inject("send", sockfd, detail);
        
        g_stat_send_injected++;
        errno = g_send_errno;
        return -1;
    }
    
    return real_send(sockfd, buf, len, flags);
}

/* Intercepted recv() */
ssize_t recv(int sockfd, void *buf, size_t len, int flags) {
    init_config();
    
    if (!g_enabled || !real_recv) {
        return real_recv ? real_recv(sockfd, buf, len, flags) : -1;
    }
    
    if (!is_targeted_fd(sockfd) && g_target_port != 0) {
        return real_recv(sockfd, buf, len, flags);
    }
    
    add_latency();
    
    if (should_inject(g_recv_fail_rate)) {
        char detail[128];
        snprintf(detail, sizeof(detail), "-> %s", errno_name(g_recv_errno));
        log_inject("recv", sockfd, detail);
        
        g_stat_recv_injected++;
        errno = g_recv_errno;
        return -1;
    }
    
    ssize_t ret = real_recv(sockfd, buf, len, flags);
    
    /* Short read injection */
    if (ret > 1 && should_inject(g_recv_short_rate)) {
        ssize_t short_len = 1 + (rand() % ((ret + 1) / 2));
        char detail[128];
        snprintf(detail, sizeof(detail), "short read %zd -> %zd", ret, short_len);
        log_inject("recv", sockfd, detail);
        
        g_stat_short_reads++;
        return short_len;
    }
    
    return ret;
}

/* Intercepted write() - for socket writes */
ssize_t write(int fd, const void *buf, size_t count) {
    init_config();
    
    if (!g_enabled || !real_write) {
        return real_write ? real_write(fd, buf, count) : -1;
    }
    
    /* Only inject for targeted sockets (fd > 2 to skip stdin/out/err) */
    if (fd > 2 && is_targeted_fd(fd) && should_inject(g_send_fail_rate)) {
        char detail[128];
        snprintf(detail, sizeof(detail), "-> %s (count=%zu)", 
                 errno_name(g_send_errno), count);
        log_inject("write", fd, detail);
        
        g_stat_send_injected++;
        errno = g_send_errno;
        return -1;
    }
    
    return real_write(fd, buf, count);
}

/* Intercepted read() - for socket reads */
ssize_t read(int fd, void *buf, size_t count) {
    init_config();
    
    if (!g_enabled || !real_read) {
        return real_read ? real_read(fd, buf, count) : -1;
    }
    
    /* Only inject for targeted sockets */
    if (fd > 2 && is_targeted_fd(fd)) {
        add_latency();
        
        if (should_inject(g_recv_fail_rate)) {
            char detail[128];
            snprintf(detail, sizeof(detail), "-> %s", errno_name(g_recv_errno));
            log_inject("read", fd, detail);
            
            g_stat_recv_injected++;
            errno = g_recv_errno;
            return -1;
        }
    }
    
    ssize_t ret = real_read(fd, buf, count);
    
    /* Short read injection for sockets */
    if (fd > 2 && is_targeted_fd(fd) && ret > 1 && should_inject(g_recv_short_rate)) {
        ssize_t short_len = 1 + (rand() % ((ret + 1) / 2));
        char detail[128];
        snprintf(detail, sizeof(detail), "short read %zd -> %zd", ret, short_len);
        log_inject("read", fd, detail);
        
        g_stat_short_reads++;
        return short_len;
    }
    
    return ret;
}

/* Intercepted open() - for file I/O faults */
int open(const char *pathname, int flags, ...) {
    init_config();
    
    mode_t mode = 0;
    if (flags & O_CREAT) {
        va_list ap;
        va_start(ap, flags);
        mode = va_arg(ap, mode_t);
        va_end(ap);
    }
    
    if (!g_enabled || !real_open) {
        return real_open ? real_open(pathname, flags, mode) : -1;
    }
    
    if (should_inject(g_open_fail_rate)) {
        char detail[256];
        snprintf(detail, sizeof(detail), "-> %s (path=%s)", 
                 errno_name(g_open_errno), pathname);
        log_inject("open", -1, detail);
        
        errno = g_open_errno;
        return -1;
    }
    
    return real_open(pathname, flags, mode);
}

/* Intercepted close() - cleanup tracking */
int close(int fd) {
    init_config();
    
    unmark_targeted_fd(fd);
    
    if (real_close) {
        return real_close(fd);
    }
    return -1;
}

/* Print statistics on library unload */
__attribute__((destructor))
static void print_stats(void) {
    if (g_log_file && g_enabled) {
        fprintf(g_log_file, "[STATS] connect_injected=%lu send_injected=%lu "
                "recv_injected=%lu short_reads=%lu\n",
                g_stat_connect_injected, g_stat_send_injected,
                g_stat_recv_injected, g_stat_short_reads);
        fclose(g_log_file);
    }
}
