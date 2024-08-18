import jwt
from datetime import datetime , timezone, timedelta
from functools import wraps
from flask import request, jsonify
from config import JWT_SECRET_KEY
from sqlalchemy import Table, MetaData, update 
from sqlalchemy.sql import select, insert



def jwt_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if auth_header:
            try:
                # Extract token from Bearer header
                token = auth_header.split(" ")[1]
                # Decode the JWT token
                payload = decode_jwt(token)
                # Add payload to the request context
                request.jwt_payload = payload
            except Exception as e:
                return jsonify({"message": str(e)}), 401
        else:
            return jsonify({"message": "Authorization header is missing"}), 401

        return f(*args, **kwargs)
    
    return decorated_function


def encode_jwt(user_id, key_id,plan_id, expiration_minutes=60):
    try:
        # Define the payload with email and key_id
        payload = {
            'user_id': user_id,
            'key_id': key_id,
            "plan_id": plan_id,
            'exp': datetime.now(timezone.utc) + timedelta(minutes=expiration_minutes)
        }
        
        # Encode the payload using the secret key
        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')
        
        return token
    except Exception as e:
        print(f"Error encoding JWT: {e}")
        return None


def decode_jwt(token):
    try:
        # Decode the JWT token
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise Exception("Token has expired")
    except jwt.InvalidTokenError:
        raise Exception("Invalid token")
    

def is_allowed_hit(db_engine):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):

            payload = request.jwt_payload
            if 'user_id' in payload:
                user_id = payload['user_id']
            else:
                user_id = None

            if 'key_id' in payload:
                key_id = payload['key_id']
            else:
                key_id =None
            

            if key_id ==None:
                return jsonify({"message": "You do not have any active plan, please select one"}),400
                

            
            metadata = MetaData()
            keys = Table('keys', metadata, autoload_with=db_engine)
            query = select(keys.c.user_id,keys.c.is_active,keys.c.quota_left).where(keys.c.id ==key_id)

            
            
            with db_engine.connect() as connection:
                result = connection.execute(query).fetchone()
                if result is None:
                    return jsonify({"message": "Either your plan is expired or does not exists"}),400
                else:
                    is_active = result[1]
                    quota_left = result[2]
                    if user_id != result[0] or is_active ==False:
                        return jsonify({"message": "You do not have any active plan"}),400
                    elif quota_left ==0:
                        return jsonify({"message": "No Quota left"}),400

            return f(*args, **kwargs)
        return decorated_function
    return decorator    


def is_plan_active(db_engine):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args,**kwargs):
            payload = request.jwt_payload

            if 'key_id' in payload:
                key_id = payload['key_id']
            else:
                key_id =None
            

            if key_id ==None:
                return jsonify({"message": "You do not have any active plan, please select one"}),400
                

            
            metadata = MetaData()
            keys = Table('keys', metadata, autoload_with=db_engine)
            query = select(keys.c.is_active).where(keys.c.id ==key_id)

            
            
            with db_engine.connect() as connection:
                result = connection.execute(query).fetchone()
                if result is None:
                    return jsonify({"message": "Either your plan is expired or does not exists"}),400
                else:
                    is_plan_active = result[0]
                    if not is_plan_active:
                        return jsonify({"message": "You do not have any active plan, please select one"}),400

            return f(*args, **kwargs)
        return decorated_function
    
    return decorator

def log_request(db_engine,parms):
    metadata = MetaData()
    requests_table = Table('requests', metadata, autoload_with=db_engine)
    keys_table = Table('keys', metadata, autoload_with=db_engine)

    payload = {
        'endpoint': parms['endpoint'],
        'key_used': parms['key_used'],
        'access_at': datetime.now(timezone.utc),
        'status': parms['status'],
        'user_id': parms['user_id']
    }
    
    with db_engine.connect() as connection:
        stmt = insert(requests_table).values(payload)
        connection.execute(stmt)
        if parms['status'] == 'Success':
            stm = update(keys_table).where(keys_table.c.id ==parms['key_used']).values(quota_left=keys_table.c.quota_left-1)
            connection.execute(stm)
        connection.commit()
