# lifeAI
NIC homework assignment
# Hướng dẫn chạy LifeAI Pipeline System

## Yêu cầu hệ thống

1. **PostgreSQL** - Database server
2. **Redis** - Message broker cho Celery
3. **Python 3.8+** với các packages đã cài đặt

## Các bước chạy code
### Bước 1: Điền các thông tin trong file .env
### Bước 2: Chạy worker celery
``` bash
celery -A celery_app worker --pool=solo --loglevel=info
```
### Bước 3: Chạy fastAPI
``` bash
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```
## Sử dụng API

### 1. Tạo một pipeline run mới

```bash
curl -X POST "http://localhost:8000/api/runs" \
  -H "Content-Type: application/json" \
  -d '{
    "objective": "Generate drug-like molecules; maximize QED; keep <= 1 rule violation.",
    "seeds": ["CCO", "c1ccccc1"],
    "rounds": 2,
    "candidates_per_round": 50,
    "top_k": 10,
    "random_seed": 42,
    "filters": {
      "mw": 500,
      "logp": 5,
      "hbd": 5,
      "hba": 10,
      "tpsa": 140,
      "max_violations": 1
    }
  }'
```

### 2. Kiểm tra status của run

```bash
curl http://localhost:8000/api/runs/{run_id}
```

### 3. Lấy kết quả

```bash
curl http://localhost:8000/api/runs/{run_id}/results
```

### 4. Xem traces (audit trail)

```bash
curl http://localhost:8000/api/runs/{run_id}/traces
```
