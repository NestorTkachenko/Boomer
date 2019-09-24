#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging
from collections import Counter
import math

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


        requests = []
        
        random.shuffle(needed_pieces)


        # records the total number of each piece
        total_piece_count = dict()

        # record which pieces are available from each peer
        for peer in peers:
            av_set = set(peer.available_pieces)
            for piece in av_set:
                # add piece to dictionary if not already present
                if piece not in total_piece_count.keys():
                    total_piece_count[piece] = [1, [peer.id]]
                else:
                # add to total piece count, and record that this peer has it
                    total_piece_count[piece][0] += 1
                    total_piece_count[piece][1].append(peer.id)

        # requests all available pieces from all peers
        for peer in peers:
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set)
            n = min(self.max_requests, len(isect))

            # request all available pieces if possible
            if self.max_requests >= len(isect):
                for piece in isect:
                    start_block = self.pieces[piece]
                    r = Request(self.id, peer.id, piece, start_block)
                    requests.append(r)

            # if available pieces exceed max_requests, sort by rarity
            else:
                # make a list of pieces and rarity from dictionary
                piece_rarity = []
                for piece in isect:
                    piece_rarity.append((total_piece_count[piece][0], piece))

                # randomize so peers don't have the same priority for equally rare pieces
                random.shuffle(piece_rarity)
                # sort from rarest to most common
                piece_rarity.sort(key = lambda x: x[0])
                # get n rarest pieces and then shuffle for symmetry breaking
                pieces = [x[1] for x in piece_rarity[:n]]
                random.shuffle(pieces)

                for piece in pieces:
                    start_block = self.pieces[piece]
                    r = Request(self.id, peer.id, piece, start_block)
                    requests.append(r)
        return requests

    def uploads(self, requests, peers, history):

        slots = 4
        round = history.current_round()


        if round >= 2:
            # get download histories of previous rounds
            dl_history1 = history.downloads[round-1]
            dl_history2 = history.downloads[round-2]
            dl_history = dict()

            # fill in dictionary with how many blocks each peer has contributed last 2 turns
            for down in dl_history1:
                source_id = down.from_id
                if source_id not in dl_history.keys():
                    dl_history[source_id] = down.blocks
                else:
                    dl_history[source_id] += down.blocks

            for down in dl_history2:
                source_id = down.from_id
                if source_id not in dl_history.keys():
                    dl_history[source_id] = down.blocks
                else:
                    dl_history[source_id] += down.blocks

        if len(requests) == 0:
            #logging.debug("No one wants my pieces!")
            chosen = []
            bws = []

        else:
            if round >= 2:
                # rank received requests by upload contribution
                all_requesters = []
                requesters_upload = []
                chosen = []

                # make list of all peers making requests
                for request in requests:
                    request_id = request.requester_id
                    if request_id not in all_requesters:
                        all_requesters.append(request_id)

                # make list of how much each peer requested
                for requester in all_requesters:
                    if requester not in dl_history.keys():
                        requesters_upload.append((0, requester))
                    else:
                        requesters_upload.append((dl_history[requester], requester))


                # sort from highest upload contribution to least, and take top 3 requesters
                requesters_upload.sort(key = lambda x:x[0], reverse=True)
                chosen = [x[1] for x in requesters_upload[:slots-2]]

                #logging.debug("Uploads: %s" % uploads)
                #!!! UNCHOKE 3 EVERY 3 MOVES, 4 OTHERWISE^^
                

                # get rid of chosen requests from request list
                for request in requests:
                    if request.requester_id in chosen:
                        requests.remove(request)

                

                # optimistic unchoke every 3 turns
                if round%3 != 0:
                    if len(requests) > 0:
                        # optimistically unchoke random request
                        random_request = random.choice(requests)
                        chosen.append(random_request.requester_id)
                        requests.remove(random_request)
                else:
                    if len(requests) > 0:
                        random_request = random.choice(requests)
                        chosen.append(random_request.requester_id)
                        requests.remove(random_request)

                # fill remaining spots with random requests
                while len(chosen) < slots and len(requests) > 0:
                    random_request = random.choice(requests)
                    chosen.append(random_request.requester_id)
                    requests.remove(random_request)
                    

            bws = even_split(self.up_bw, len(chosen))
        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]


        return uploads
