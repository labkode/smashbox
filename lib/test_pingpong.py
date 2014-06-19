from smashbox.utilities import * 
from smashbox.utilities.hash_files import count_files

import glob

__doc__ = """ Test parallel upload of the same file by two clients.

The name of the test derives from the behaviour observed with eos
webdav endpoint: two file versions would ping-pong between the
clients.

This documents an interesting semantics of the system: parallel upload
into the same destination file should both succeed without creating a
conflict -- this is because the ETAG check happens while processing
the headers and not while commiting the file to the strorage.

So one file will appear as "lost" - but in fact is recoverable via the versions.

EOS webdav endpoint behaviour is like this. Also, Owncloud6 behaviour
(with EOS fuse-mounted datadirectory on cbox06) is like this.

Owncloud 5 server is different and fails one of the initial uploads with Bad Request:

Logfile: test_pingpong/pong-ocsync.step02.cnt000.log

"PUT"    QUrl( "https://box.server/remote.php/webdav/BALL

<d:error xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns">
  <s:exception>Sabre_DAV_Exception_BadRequest</s:exception>
  <s:message>expected filesize 5000000 got </s:message>
  <s:sabredav-version>1.7.6</s:sabredav-version>
</d:error>


"""

filesizeKB = int(config.get('pinpong_filesizeKB',5000))


@add_worker
def ping(step):
    
    reset_owncloud_account()
    reset_rundir()

    shared = reflection.getSharedObject()

    seen_files = set()
    
    step(1,'initialize')

    d = make_workdir()

    createfile(os.path.join(d,'BALL'),'0',count=1000,bs=filesizeKB)

    BALL = md5sum(os.path.join(d,'BALL'))
    logger.info('BALL: %s',BALL)

    shared['PING_BALL'] = BALL

    # we do exactly 2 sync runs
    # in the first one the files are uploaded in parallel -- note: no conflict created!
    # in the second one either ping or pong grabs and downloads the most recent version of the file
    step(2,'first sync')
    run_ocsync(d,N=2)
    LAST_BALL = md5sum(os.path.join(d,'BALL'))
    logger.info('LAST_BALL: %s',LAST_BALL)

    for i in range(3,10):
        seen_files.add(LAST_BALL)
        step(i,'next sync')
        run_ocsync(d,N=1)
        BALL = md5sum(os.path.join(d,'BALL'))
        logger.info('BALL: %s',BALL)
        error_check( BALL == LAST_BALL, "the file is ping-ponging between the clients")
        LAST_BALL = BALL

    shared['PING_SEEN_FILES'] = len(seen_files)

    step(90, "Verification if files moved at all")

    error_check( len(glob.glob(os.path.join(d,'*_conflict-*-*'))) == 0, "Conflicts found!")

@add_worker
def pong(step):

    seen_files = set()

    step(1,'initialize')

    d = make_workdir()
    shared = reflection.getSharedObject()

    createfile(os.path.join(d,'BALL'),'1',count=1000,bs=filesizeKB)

    BALL = md5sum(os.path.join(d,'BALL'))
    logger.info('BALL: %s',BALL)

    shared['PONG_BALL'] = BALL

    step(2,'first sync')
    run_ocsync(d,N=2)
    LAST_BALL = md5sum(os.path.join(d,'BALL'))
    logger.info('LAST_BALL: %s',LAST_BALL)

    for i in range(3,10):
        seen_files.add(LAST_BALL)
        step(i,'next sync')
        run_ocsync(d,N=1)
        BALL = md5sum(os.path.join(d,'BALL'))
        logger.info('BALL: %s',BALL)
        error_check( BALL == LAST_BALL, "the file is ping-ponging between the clients")
        LAST_BALL = BALL

    step(90, "Verification if files moved at all")

    PING_SEEN_FILES = shared['PING_SEEN_FILES']
    PONG_SEEN_FILES = len(seen_files)

    logger.info('PING_SEEN_FILES: %d',PING_SEEN_FILES)
    logger.info('PONG_SEEN_FILES: %d',PONG_SEEN_FILES)


    # one client should see exactly one file version and the other one exactly two versions
    if not ( (PING_SEEN_FILES==1 and PONG_SEEN_FILES==2) or (PING_SEEN_FILES==2 and PONG_SEEN_FILES==1) ):

        if PING_SEEN_FILES==2 and PONG_SEEN_FILES==2:
            error_check(False, "File was pingponging")
        else:
            if PING_SEEN_FILES==1 or PONG_SEEN_FILES==1:
                error_check(False, "File was not transmitted by one or both clients")
            if PING_SEEN_FILES>2 or PONG_SEEN_FILES>2:
                error_check(False, "Too many file versions -- possible data corruption")

    # FIXME: check if versions have been correctly created on the server


    error_check( len(glob.glob(os.path.join(d,'*_conflict-*-*'))) == 0, "Conflicts found!")
