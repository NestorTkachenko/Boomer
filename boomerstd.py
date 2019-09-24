#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging
from collections import Counter

from messages import Upload, Request
from util import even_split
from peer import Peer

class BoomerStd(Peer):
    def post_init(self):
        print "post_init(): %s here!" % self.id
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"
    
    def requests(self, peers, history):
        """
        peers: available info about the peers (who has what pieces)
        history: what's happened so far as far as this peer can see

        returns: a list of Request() objects

        This will be called after update_pieces() with the most recent state.
        """
        needed = lambda i: self.pieces[i] < self.conf.blocks_per_piece
        needed_pieces = filter(needed, range(len(self.pieces)))
        np_set = set(needed_pieces)  # sets support fast intersection ops.


        #logging.debug("%s here: still need pieces %s" % (
        #    self.id, needed_pieces))

        #logging.debug("%s still here. Here are some peers:" % self.id)
        #for p in peers:
        #    logging.debug("id: %s, available pieces: %s" % (p.id, p.available_pieces))


        #!!!find rarest piece
        pieceList = []
        rareList = []
        for p in peers:
            pieceList = pieceList + list(p.available_pieces)

        least = Counter( pieceList ).most_common()[::-1]

        #logging.debug("least: %s" % least)

        lowestFrequency = least[0][1]
        for i in least:
            if i[1] == lowestFrequency:
                rareList.append(i[0])
            else:
                break

        #!!!rareList contains the rarest pieces, and least is pieces sorted rarest first
            
        #logging.debug("Rarest Pieces: %s" % rareList)


        

        #logging.debug("And look, I have my entire history available too:")
        #logging.debug("look at the AgentHistory class in history.py for details")
        #logging.debug(str(history))

        requests = []   # We'll put all the things we want here
        # Symmetry breaking is good...
        random.shuffle(needed_pieces)
        
        # Sort peers by id.  This is probably not a useful sort, but other 
        # sorts might be useful

        #!!!Sorts peers, with the ones with the most rarest pieces coming first
        #peers.sort(key=lambda p: len(p.available_pieces & set(rareList)), reverse = True)
             
        # request all available pieces from all peers!
        # (up to self.max_requests from each)
        for peer in peers:
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set)
            n = min(self.max_requests, len(isect))

            #logging.debug("Intersection: %s" % isect)            
            # More symmetry breaking -- ask for random pieces.
            # This would be the place to try fancier piece-requesting strategies
            # to avoid getting the same thing from multiple peers at a time.

            #!!!Here we go through the rarest pieces and request the ones we need
            
            

            for p in least:
                num = 0
                if p[0] in isect:
                    start_block = self.pieces[p[0]]
                    r = Request(self.id, peer.id, p[0], start_block)
                    requests.append(r)
                    num = num + 1
                if num >= n:
                    break
            
        #logging.debug("Requests: %s" % requests)
        return requests

    def uploads(self, requests, peers, history):
        """
        requests -- a list of the requests for this peer for this round
        peers -- available info about all the peers
        history -- history for all previous rounds

        returns: list of Upload objects.

        In each round, this will be called after requests().
        """

        #logging.debug("History: %s" % str(history.downloads))

        round = history.current_round()
        #logging.debug("%s again.  It's round %d." % (
        #    self.id, round))
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.

        #!!!Make priority order for peers based on download contribution last 2 turns
        priority = []
        if round > 0:
            for d in history.downloads[round-1]:
                if not (any(d.from_id in i for i in priority)):
                    #logging.debug("Added to priority: %s" % d.from_id)
                    priority.append((d.from_id,d.blocks))
                else:
                    for t in range(len(priority)):
                        if priority[t][0] == d.from_id:
                            priority[t] = (priority[t][0],priority[t][1] + d.blocks)
                    #logging.debug("Added priority pts: %s" % d.from_id)

        if round > 1:
            for d in history.downloads[round-2]:
                if not (any(d.from_id in i for i in priority)):
                    #logging.debug("Added to priority: %s" % d.from_id)
                    priority.append((d.from_id,d.blocks))
                else:
                    for t in range(len(priority)):
                        if priority[t][0] == d.from_id:
                            priority[t] = (priority[t][0],priority[t][1] + d.blocks)
                    #logging.debug("Added priority pts: %s" % d.from_id)

        priority.sort(key=lambda p: p[1], reverse = True)
        #!!!priority ranks the highest contributors in order
        
        #logging.debug("Priority List: %s" % priority)
        
        
        uploads = []
        
        if len(requests) == 0:
            #logging.debug("No one wants my pieces!")
            chosen = []
            bws = []
        else:
            #logging.debug("Still here: uploading to a random peer")
            # change my internal state for no reason
            self.dummy_state["cake"] = "pie"

            usedbw = 0
            if round % 2 == 0:
                usedbw = 1

            #logging.debug("Priority: %s" % priority)
            #logging.debug("Requests: %s" % requests)
            
            for p in priority:
                for r in requests:
                    if p[0] == r.requester_id:
                        uploads.append(Upload(self.id, p[0],1))
                        usedbw = usedbw + 1
                    if usedbw >= self.up_bw:
                        break
                if usedbw >= self.up_bw:
                    break

            if usedbw < self.up_bw:
                for r in requests:
                    if not (any(r.requester_id in i for i in priority)):
                        uploads.append(Upload(self.id, r.requester_id,1))
                        usedbw = usedbw + 1
                    if usedbw >= self.up_bw:
                        break
            #!!! upload to highest contributors

            #!!! for every other round, pick random peer to upload to
            #!!! optimistic unchoking

            random.shuffle(requests)
            if round % 2 == 0:
                for r in requests:
                    found = False
                    for u in uploads:
                        if u.to_id == r.requester_id:
                            found = True
                            break
                    if found == False:
                        uploads.append(Upload(self.id, r.requester_id,1))
                        break

            #request = random.choice(requests)
            #chosen = [request.requester_id]
            # Evenly "split" my upload bandwidth among the one chosen requester
            #bws = even_split(self.up_bw, len(chosen))
            

        # create actual uploads out of the list of peer ids and bandwidths
        #uploads = [Upload(self.id, peer_id, bw)
        #           for (peer_id, bw) in zip(chosen, bws)]

        #logging.debug("Uploads: %s" % uploads)
            
        return uploads
