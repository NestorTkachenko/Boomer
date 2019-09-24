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
        self.alpha = .2
    
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


        logging.debug("%s here: still need pieces %s" % (
            self.id, needed_pieces))

        logging.debug("%s still here. Here are some peers:" % self.id)
        for p in peers:
            logging.debug("id: %s, available pieces: %s" % (p.id, p.available_pieces))

        # logging.debug("And look, I have my entire history available too:")
        # logging.debug("look at the AgentHistory class in history.py for details")
        # logging.debug(str(history))

        requests = []   # We'll put all the things we want here
        # Symmetry breaking is good...
        random.shuffle(needed_pieces)
        
        # Sort peers by id.  This is probably not a useful sort, but other 
        # sorts might be useful
        peers.sort(key=lambda p: p.id)
        # request all available pieces from all peers!
        # (up to self.max_requests from each)
        for peer in peers:
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set)
            n = min(self.max_requests, len(isect))
            # More symmetry breaking -- ask for random pieces.
            # This would be the place to try fancier piece-requesting strategies
            # to avoid getting the same thing from multiple peers at a time.
            for piece_id in random.sample(isect, n):
                # aha! The peer has this piece! Request it.
                # which part of the piece do we need next?
                # (must get the next-needed blocks in order)
                start_block = self.pieces[piece_id]
                r = Request(self.id, peer.id, piece_id, start_block)
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
                        peer_dict['u'] = peer_dict['u'] * (1-self.alpha)

        logging.debug("\npeer_ratios for {}:\n{}\n".format(self.id, self.peer_ratios))

        chosen = []
        bws = []
        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
        else:
            logging.debug("Still here: uploading to a (hopefully not) random peer")
            # change my internal state for no reason
            # self.dummy_state["cake"] = "pie"

            bw_left = self.up_bw
            upload_to = sorted([(peer_id, d['d']/d['u'], d['u']) for peer_id, d in self.peer_ratios.items()], key=lambda p:p[1], reverse=True)
            for peer_id, ratio, bw in upload_to:
                if (bw_left - bw) < 0 or 'Seed' in peer_id:
                    continue
                chosen.append(peer_id)
                bws.append(bw)
                bw_left -= bw

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
