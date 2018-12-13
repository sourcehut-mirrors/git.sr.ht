try:
    from redis import StrictRedis as Redis
except ImportError:
    from redis import Redis

redis = Redis()
