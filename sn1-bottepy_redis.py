#!/usr/bin/python
# -*- coding: utf-8 -*-

import traceback
import os, sys
import time
import json
import itertools
import redis
import bottle
from bottle import request, response, static_file

execdir = os.path.dirname(sys.argv[0])

app = bottle.Bottle()


@app.hook('after_request')
def enable_cors():
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'PUT, GET, POST, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token, Authentication'


db = redis.StrictRedis(db=5)

# authentication code start


import hashlib

@app.route('/signup', method='POST')
def dosignup():
    req = json.load(bottle.request.body)
    uid, password, profile = req['uid'], req['password'], req['profile']
    
    existing = db.hget('accounts', uid)
    
    if existing is not None:
        return {'status': 'error', 'code': 400, 'message': 'account uid exists %s' %uid}
    
    
    hash_ = hashlib.sha1(password).hexdigest()
    
    account = {'password': hash_, 'profile': json.dumps(profile) }
    
    db.hset('accounts', uid, json.dumps(account))
    
    return {'status': 'success', 'code': 0}

@app.route('/login', method='POST')
def dologin():
    req = json.load(bottle.request.body)
    uid, password = req['uid'], req['password']
    
    hash_ = hashlib.sha1(password).hexdigest()
    
    account = db.hget('accounts', uid)
    
    if account is None:
        return {'status': 'error', 'code': 404, 'message': 'no account with %s' %uid}
    
    account = json.loads(account)
    if not account['password'] == hash_:
        # wrong password
        return bottle.HTTPResponse(status=403)
    
    # login successful
    del account['password']
    
    sessionid = hashlib.sha1('%s%s%f' %(uid, hash_, time.time())).hexdigest()
    
    db.set('session-%s' %sessionid, uid)
    
    db.expire('session-%s' %sessionid, 3 * 3600) # expires in x hours
    
    return {'status': 'success', 'code': 0, 'account': account, 'sessionid': sessionid }


def authinfofromheader(sessionid):
    uid = db.get('session-%s' %sessionid)
    if uid is None: return False, None
    return True, {'uid': uid, 'role': None}


# authentication code end


@app.route('/posts', method='GET')
def getposts():
    authenticated, authinfo = authinfofromheader( bottle.request.headers.get('Authentication') )
    
    
    if not authenticated:
        return bottle.HTTPResponse(status=403)
    
    dbname = "%s" %authinfo['id']
    
    authuid, authrole = authinfo['uid'], authinfo['role']

    result = db.hgetall ('%s.posts' %( dbname ) )
    
    result = [ [Id]+json.loads(row) for Id, row in result.items() ]
    
    
    
    ID, AUTHOR,TEXT,TIMESTAMP,REPLYTO = range(5)
    result = [record for record in result if authuid == record[AUTHOR] or record[AUTHOR] in getcurrentuserfollows()]
    
    return {'status': 'success', 'code': 0, 'data': result }



@app.route('/posts', method=['POST', 'OPTIONS'])
def alterposts():
    if request.method == 'OPTIONS':
        return {}

    authenticated, authinfo = authinfofromheader( bottle.request.headers.get('Authentication') )
    
    
    if not authenticated:
        return bottle.HTTPResponse(status=403)
    
    dbname = "%s" %authinfo['id']

    authuid, authrole = authinfo['uid'], authinfo['role']

    req = json.load(bottle.request.body)
    
    # enforces
    req['author'] = authuid
    req['timestamp'] = now

    #print "received request", req
    if 'id' in req:
        Id = req['id']
        if '.operation' in req and req['.operation'] == 'DELETE':
            if authrole == 'principal':
                db.hdel('%s.posts' %(dbname), Id)
                return {'status': 'success', 'code': 0}
            else:
                return bottle.HTTPResponse(status=403)
    else:
        Id = db.incr('%s.seqposts' %(dbname)) + 200

        
        
    try:
        fields = ["author", "text", "timestamp", "replyto"]
        db.hset('%s.posts' %(dbname), Id, json.dumps([req[field] for field in  fields]) )
    except:
        #raise Exception('POST error')
        print(traceback.format_exc())
        return {'status': 'error', 'code': 2}
    
    return {'status': 'success', 'code': 0, 'id': Id}



@app.route('/follows', method='GET')
def getfollows():
    authenticated, authinfo = authinfofromheader( bottle.request.headers.get('Authentication') )
    
    
    if not authenticated:
        return bottle.HTTPResponse(status=403)
    
    dbname = "%s" %authinfo['id']
    
    authuid, authrole = authinfo['uid'], authinfo['role']

    result = db.hgetall ('%s.follows' %( dbname ) )
    
    result = [ [Id]+json.loads(row) for Id, row in result.items() ]
    
    
    
    
    
    return {'status': 'success', 'code': 0, 'data': result }



@app.route('/follows', method=['POST', 'OPTIONS'])
def alterfollows():
    if request.method == 'OPTIONS':
        return {}

    authenticated, authinfo = authinfofromheader( bottle.request.headers.get('Authentication') )
    
    
    if not authenticated:
        return bottle.HTTPResponse(status=403)
    
    dbname = "%s" %authinfo['id']

    authuid, authrole = authinfo['uid'], authinfo['role']

    req = json.load(bottle.request.body)
    
    # enforces
    req['follower'] = authuid
    req['timestamp'] = now

    #print "received request", req
    if 'id' in req:
        Id = req['id']
        if '.operation' in req and req['.operation'] == 'DELETE':
            if authrole == 'principal':
                db.hdel('%s.follows' %(dbname), Id)
                return {'status': 'success', 'code': 0}
            else:
                return bottle.HTTPResponse(status=403)
    else:
        Id = db.incr('%s.seqfollows' %(dbname)) + 200

        
        
    try:
        fields = ["follower", "followed", "timestamp"]
        db.hset('%s.follows' %(dbname), Id, json.dumps([req[field] for field in  fields]) )
    except:
        #raise Exception('POST error')
        print(traceback.format_exc())
        return {'status': 'error', 'code': 2}
    
    return {'status': 'success', 'code': 0, 'id': Id}



@app.route('/currentuserfollows', method='GET')
def getcurrentuserfollows():
    authenticated, authinfo = authinfofromheader( bottle.request.headers.get('Authentication') )
    
    
    if not authenticated:
        return bottle.HTTPResponse(status=403)
    
    dbname = "%s" %authinfo['id']
    
    authuid, authrole = authinfo['uid'], authinfo['role']

    result = db.hgetall ('%s.currentuserfollows' %( dbname ) )
    
    result = [ [Id]+json.loads(row) for Id, row in result.items() ]
    
    follows = db.hgetall ('%s.follows' %( dbname ) )
    follows = [[Id]+json.loads(row) for Id, row in follows.items()]
    return [record_followed for (follower,followed,timestamp) in follows if record_follower == authuid]
    
    
    
    return {'status': 'success', 'code': 0, 'data': result }



@app.route('/documentation.txt', method='GET')
def getdocumentation():
    response.headers['Content-Type'] = 'text/plain'
    return '''
The API provides the endpoints listed below.
POST endpoints expect *all* fields to be sent, optional ones should be set to 
null. If the post parameters contain a valid `id` field, the request modifies 
the existing record instead of creating  a new one. 
GET endpoints return a list/array of record values *without* the field names.
The order of these values is documented in this document.



* GET posts
    response.data: list of (id (number),
                            author (text),
                            text (text),
                            timestamp (text),
                            replyto (text))

            

* POST posts
    post body (JSON): {author: ...,
                       text: ...,
                       timestamp: ...,
                       replyto: ...}
    response: status, code, id
            

* GET follows
    response.data: list of (id (number),
                            follower (text),
                            followed (text),
                            timestamp (text))

            

* POST follows
    post body (JSON): {follower: ...,
                       followed: ...,
                       timestamp: ...}
    response: status, code, id
            

* GET currentuserfollows
    response.data: list of (id (number),
                            follows (text))

            

* POST currentuserfollows
    post body (JSON): {follows: ...}
    response: status, code, id
            '''


@app.route('/upload/<filename>', method='GET')
def serveuploadfile(filename):
    
    authenticated, authinfo = authinfofromheader( bottle.request.headers.get('Authentication') )
    
    
    if not authenticated:
        return bottle.HTTPResponse(status=403)
    
    dbname = "%s" %authinfo['id']
    
    targetdir = 'upload/%s' %dbname.replace('/', '--')
    
    return static_file(filename, root=targetdir)
    
    
@app.route('/upload/<filename>', method=['POST', 'OPTIONS'])
def uploadfile(filename):
    if request.method == 'OPTIONS':
        return {}

    authenticated, authinfo = authinfofromheader( bottle.request.headers.get('Authentication') )
    
    
    if not authenticated:
        return bottle.HTTPResponse(status=403)
    
    dbname = "%s" %authinfo['id']
    #import cgi
    #print cgi.FieldStorage(request.body)
    #print request.body.read()
    #print request.files.keys()
    #upload = request.files.get('upload')
    
    name, ext = os.path.splitext(filename)
    
    if ext in ('.sh','.php','.py', '.exe', '.elf'):
        return {'status': 'error', 'code': 100}
        
    
    targetdir = 'upload/%s' %dbname.replace('/', '--')
    
    if not os.path.isdir(targetdir): os.mkdir(targetdir)
    
    filename = os.path.join(targetdir, filename)

    with open(filename, 'w+') as f: f.write(request.body.read())
    
    return {'status': 'success', 'code': 0, 'path': filename}



if __name__ == '__main__':
    print("starting ", execdir)
    
    HOST, DEBUG = '0.0.0.0', True
    
    try:
        bottle.run(app=app, host='0.0.0.0', port=int(sys.argv[1]), debug=False, server='bjoern')
        #bottle.run(app=app, host='0.0.0.0', port=int(sys.argv[1]), debug=True)
    except:
        print("---------\nops, something went south!! send the following text to the developer\n%s"   %traceback.format_exc())
