#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging
import math

from messages import Upload, Request
from util import even_split
from peer import Peer

class BoomerTyrant(Peer):
    def post_init(self):
        print "post_init(): %s here!" % self.id
        self.peer_ratios = dict()
        self.gamma = .1
        self.r = 3
        self.alpha = .3
    
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

        logging.debug("\nrequests for {}:\n{}\n".format(self.id, requests))

        return requests

    def uploads(self, requests, peers, history):
        """
        requests -- a list of the requests for this peer for this round
        peers -- available info about all the peers
        history -- history for all previous rounds

        returns: list of Upload objects.

        In each round, this will be called after requests().
        """

        round = history.current_round()


        logging.debug("%s again.  It's round %d." % (
            self.id, round))
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.

        if round == 0:
            if not self.peer_ratios:
                for peer in peers:
                    self.peer_ratios[peer.id] = dict()
                    self.peer_ratios[peer.id]['d'] = 1.0
                    self.peer_ratios[peer.id]['u'] = 1.0
        else:
            # update download rate
            add_downloads = dict()
            for download in history.downloads[-1]:
                if download.from_id not in add_downloads:
                    add_downloads[download.from_id] = 0
                add_downloads[download.from_id] += download.blocks
            for from_id, blocks in add_downloads.items():
                self.peer_ratios[from_id]['d'] = blocks

            # update upload rate
            for peer_id, peer_dict in self.peer_ratios.items():
                if peer_id not in add_downloads:
                    peer_dict['u'] = peer_dict['u'] * (1+self.alpha)
                # unchoked for last r periods
                else:
                    unchoked = True
                    # check the last r periods
                    for i in range(min(self.r, round)):
                        # is peer in last i period
                        found_peer = False
                        for download in history.downloads[-1*(i+1)]:
                            if download.from_id == peer_id:
                                found_peer = True
                                break
                        # didn't find peer in one of last r periods
                        if not found_peer:
                            unchoked = False
                            break
                    if unchoked:
                        peer_dict['u'] = peer_dict['u'] * (1-self.gamma)

        logging.debug("\npeer_ratios for {}:\n{}\n".format(self.id, self.peer_ratios))

        chosen = []
        bws = []
        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
        else:
            logging.debug("Still here: uploading to a (hopefully not) random peer")
            # change my internal state for no reason
            # self.dummy_state["cake"] = "pie"

            peers_who_want_my_stuff = set()
            for request in requests:
                peers_who_want_my_stuff.add(request.requester_id)

            bw_left = self.up_bw
            upload_to = sorted([(peer_id, d['d']/d['u'], d['u']) for peer_id, d in self.peer_ratios.items()], key=lambda p:p[1], reverse=True)
            for peer_id, ratio, bw in upload_to:
                if bw_left <= 0:
                    break
                if peer_id not in peers_who_want_my_stuff:
                    continue
                chosen.append(peer_id)
                bws.append(min(bw_left, math.floor(bw)))
                bw_left -= min(bw_left, math.floor(bw))

            logging.debug("\npriorities for {}:\n{}".format(self.id, upload_to))

            # request = random.choice(requests)
            # chosen = [request.requester_id]
            # Evenly "split" my upload bandwidth among the one chosen requester
            # bws = even_split(self.up_bw, len(chosen))

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]

        logging.debug("\nuploads for {} with bw {}:\n{}\n{}\n".format(self.id, self.up_bw, chosen, bws))
            
        return uploads
