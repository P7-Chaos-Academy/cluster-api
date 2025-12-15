# Docker

## Build

```
sudo docker build -t cgamel/cluster-api:unique-tag .
```

## Testing

```
python -m pytest tests/ -v --cov=app --cov-report=term-missing --cov-branch
```