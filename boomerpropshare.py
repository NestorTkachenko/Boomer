#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer

class BoomerPropShare(Peer):
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

        rand_frac = 0.1
        blocks = 0
        uploads = []


        round = history.current_round()


        if round > 0:
            # previous rounds histories
            dl_history1 = history.downloads[round-1]
            dl_history = dict()

            # add to dict
            for down in dl_history1:
                source_id = down.from_id
                if source_id not in dl_history.keys():
                    dl_history[source_id] = down.blocks
                else:
                    dl_history[source_id] += down.blocks

        if len(requests) == 0:
            chosen = []
            bws = []

        else:
            # record request and upload amounts
            all_requesters = []
            uploaded = dict()
            
            # store peers who requested
            for request in requests:
                request_id = request.requester_id
                if request_id not in all_requesters:
                    all_requesters.append(request_id)

            # match peers with how much they uploaded
            for requester in all_requesters:
                if requester in dl_history.keys():
                    uploaded[requester] = dl_history[requester]

            # fine the number of blocks total
            for uploader in uploaded.keys():
                blocks += uploaded[uploader]

            # calculate bandwidth fraction for each peer
            for uploader in uploaded.keys():
                frac = (uploaded[uploader] / blocks) * (1 - rand_frac)
                uploaded[uploader] = frac

            # filter out uploaded peers to search for optimistic unchoking candidate
            rand_candidates = filter(lambda x: x not in uploaded.keys(), all_requesters)

            uploads = []
            
            # add peers to upload list with respective bandwidth allocation
            for uploader in uploaded.keys():
                frac = uploaded[uploader]
                uploads.append(Upload(self.id, uploader, int(self.up_bw * frac)))

            # add randomly selected peers with bandwidth allocation
            if len(rand_candidates) > 0:
                if len(uploads) == 0:
                    random_candidate = random.choice(rand_candidates)
                    uploads.append (Upload(self.id, random_candidate, self.up_bw))
                else:
                    random_candidate = random.choice(rand_candidates)
                    uploads.append (Upload(self.id, random_candidate, self.up_bw * rand_frac))

        return uploads
