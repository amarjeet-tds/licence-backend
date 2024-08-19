from utils import encode_jwt , format_time
from sqlalchemy import Table, MetaData, update , and_, desc
from sqlalchemy.sql import select, insert


def list_plans_fn(db_engine):
    metadata = MetaData()
    plans = Table('plans', metadata, autoload_with=db_engine)

    # Create the select query
    query = select(plans.c.id, plans.c.name, plans.c.quota)

    with db_engine.connect() as connection:
        result = connection.execute(query).fetchall()
        
        # Check if the result is empty
        if not result:
            return {"data": [], "message": "No Plan Found"}, 200
        
        # Use list comprehension to map the result
        data = [{"id": row.id, "name": row.name, "quota": row.quota} for row in result]

    return {"data": data}, 200


def create_token_fn(db_engine,parms):
    metadata = MetaData()
    users = Table('users', metadata, autoload_with=db_engine)
    query = select(users.c.id).where(users.c.name ==parms['name'])
    user_id = None
    # sanitize name
    with db_engine.connect() as connection:
        result = connection.execute(query).fetchone()
        if result is None:
            stmt = insert(users).values(name=parms['name']).returning(users.c.id)
            result = connection.execute(stmt)
            user_id = result[0]
        else:
            user_id = result[0]
        connection.commit()

    token = encode_jwt(user_id, key_id=1)
    return {"jwt_token": token},200



def activate_plan_fn(db_engine,parms):
    user_name = parms['user_name']
    plan_id = parms['plan_id']

    metadata = MetaData()
    users = Table('users', metadata, autoload_with=db_engine)
    query = select(users.c.id).where(users.c.name ==user_name)
    keys = Table('keys', metadata, autoload_with=db_engine)
    user_id = None
    key_id= None
    quota_left = None
    # sanitize name
    with db_engine.connect() as connection:
        result = connection.execute(query).fetchone()
        if result is None:
            stmt = insert(users).values(name=user_name).returning(users.c.id)
            result = connection.execute(stmt)
            user_id = result[0]
        else:
            user_id = result[0]
            if plan_id is None:
                stm = select(keys.c.plan_id).where(and_(keys.c.user_id ==user_id, keys.c.is_active == True))
                plan_res = connection.execute(stm).fetchone()
                if plan_res is not None:
                    plan_id = plan_res[0]

        plans = Table('plans', metadata, autoload_with=db_engine)
        query = select(plans.c.quota).where(plans.c.id ==plan_id)
        result = connection.execute(query).fetchone()
        if result is None:
            quota = None
        else:
            quota = result[0]
        
        if quota is not None and user_id is not None:
            
            stm = update(keys).where(keys.c.user_id ==user_id).values(is_active=False)
            connection.execute(stm)
            query = select(keys.c.id,keys.c.quota_left ).where(and_(keys.c.user_id ==user_id, keys.c.plan_id ==plan_id))
            result = connection.execute(query).fetchone()
            if result is None:
                stmt = insert(keys).values({"user_id": user_id, "plan_id": plan_id, "quota_left": quota, "is_active": True}).returning(keys.c.id)
                res = list(connection.execute(stmt))
                key_id = res[0][0]
                quota_left = quota
            else:
                key_id = result[0]
                quota_left = result[1]
                stm2 = update(keys).where(keys.c.id ==key_id).values(is_active=True)
                connection.execute(stm2)            
        connection.commit()
            
        
    token = encode_jwt(user_id, key_id,plan_id)
        
    return {"jwt_token": token, "plan_id": plan_id, "quota_left": quota_left},200

def reset_quota_fn(db_engine,parms):
    key_id = parms['key_id']
    plan_id = parms['plan_id']

    metadata = MetaData()
    plans = Table('plans', metadata, autoload_with=db_engine)
    keys_table = Table('keys', metadata, autoload_with=db_engine)

    
    
    with db_engine.connect() as connection:
        stm1 = select(plans.c.quota).where(plans.c.id == plan_id)
        result = connection.execute(stm1).fetchone()
        if result is None:
            return {"message": "This Plan does not exists"}, 400
        quota = result[0]

        stm2 = update(keys_table).where(keys_table.c.id ==key_id).values(quota_left=quota)
        connection.execute(stm2)
        connection.commit()
    return {"message": "Quota Refilled", "quota_left": quota}, 200

def user_dashboard_fn(db_engine,parms):
    key_id = parms['key_id']
    plan_id = parms['plan_id']
    data = []

    metadata = MetaData()
    requests_table = Table('requests', metadata, autoload_with=db_engine)
    with db_engine.connect() as connection:
        stm1 = select(requests_table.c.access_at, requests_table.c.status).where(requests_table.c.key_used == key_id).order_by(desc(requests_table.c.access_at))
        result = connection.execute(stm1).fetchall()
        if result is None:
            return {"data": "No Data Found"}, 200
        data = [{"access_at": el[0], "status": el[1] } for el in result]
    total_hits = 0
    success_hits = 0
    error_hits = 0 


    for d in data:
        total_hits+=1
        if d['status'].lower() == 'success':
            success_hits+=1
        else:
            error_hits+=1
    
    
    
    return { "data": {
        "plan_id": plan_id,
        "total_hits": total_hits,
        "success_hits": success_hits,
        "error_hits": error_hits,
    }},200