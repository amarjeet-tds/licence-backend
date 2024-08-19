from flask import Flask , Response,json, request
from flask_cors import CORS
from controller import activate_plan_fn, list_plans_fn, reset_quota_fn, user_dashboard_fn
from utils import jwt_required, is_allowed_hit, log_request , is_plan_active, get_left_quota_fn
from sqlalchemy import create_engine
from config import DB_USER, DB_NAME,DB_HOST,DB_PASSWORD

db_engine = create_engine(f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}')
app = Flask(__name__)
CORS(app)


@app.route('/list_plans',  methods=['GET'])
def list_plans():
    try:
        res , status =  list_plans_fn(db_engine)
        return  Response(json.dumps(res), status=status, mimetype='application/json')
    except Exception as e:
        print(e)
        return Response(json.dumps({"message":"Internal Server Error"}), status=500, mimetype='application/json')


@app.route('/activate_plan',  methods=['GET'])
def activate_plan():
    try:
        user_name =  request.args.get('user_name')
        plan_id =  request.args.get('plan_id',None)
        parms = {
            "user_name" : user_name,
            "plan_id": None
        }
        if plan_id is not None:
            parms['plan_id'] = int(plan_id)
        
        res , status =  activate_plan_fn(db_engine,parms)
        return  Response(json.dumps(res), status=status, mimetype='application/json')
    except Exception as e:
        print(e)
        return Response(json.dumps({"message":"Internal Server Error"}), status=500, mimetype='application/json')

@app.route('/reset_quota',  methods=['GET'])
@jwt_required
@is_plan_active(db_engine)
def reset_quota():
    try:
        payload = request.jwt_payload
        parms = {
            "key_id": payload['key_id'],
            "plan_id": payload['plan_id']
        }

        res , status =  reset_quota_fn(db_engine,parms)
        return  Response(json.dumps(res), status=status, mimetype='application/json')
    except Exception as e:
        print(e)
        return Response(json.dumps({"message":"Internal Server Error"}), status=500, mimetype='application/json')


@app.route('/hit_api',  methods=['GET'])
@jwt_required
@is_allowed_hit(db_engine=db_engine)
def hit_api():
    req_status = 'Pending'
    endpoint = '/get_my_name'
    try:
        payload = request.jwt_payload
        res , status =  {"data": "API Hitted successfully"}, 200
        quota_left = get_left_quota_fn(db_engine,payload['key_id'])
        res['quota_left'] = quota_left-1
        req_status = 'Success'
        return  Response(json.dumps(res), status=status, mimetype='application/json')
    except Exception as e:
        req_status = 'Error'
        print(e)
        return Response(json.dumps({"message":"Internal Server Error"}), status=500, mimetype='application/json')
    finally:
        parms = {
        'endpoint': endpoint ,
        'key_used': payload['key_id'],
        'status': req_status,
        'user_id': payload['user_id']
        }
        log_request(db_engine, parms)

@app.route('/user_dashboard',  methods=['GET'])
@jwt_required
@is_plan_active(db_engine=db_engine)
def user_dashboard():
    try:
        payload = request.jwt_payload
        parms = {
            "key_id": payload['key_id'],
            "plan_id": payload['plan_id']
        }

        res , status =  user_dashboard_fn(db_engine, parms)
        return  Response(json.dumps(res), status=status, mimetype='application/json')
    except Exception as e:
        print(e)
        return Response(json.dumps({"message":"Internal Server Error"}), status=500, mimetype='application/json')


if __name__ == '__main__':
    app.run()
