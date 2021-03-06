#!/usr/bin/env python
#
# Software License Agreement (BSD License)
#
# Copyright (c) 2009, Willow Garage, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#  * Neither the name of the Willow Garage nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import rospy
import message_filters
import threading
import itertools

class ApproximateSynchronizer(message_filters.SimpleFilter):

    def __init__(self, slop, fs, queue_size):
        message_filters.SimpleFilter.__init__(self)
        self.connectInput(fs)
        self.queue_size = queue_size
        self.lock = threading.Lock()
        self.slop = rospy.Duration.from_sec(slop)

    def connectInput(self, fs):
        self.queues = [{} for f in fs]
        self.input_connections = [f.registerCallback(self.add, q) for (f, q) in zip(fs, self.queues)]

    def add(self, msg, my_queue, msg_timeout=5):
        self.lock.acquire()
        # if message is older than 5 sec ignore
        age = rospy.Time.now() - msg.header.stamp
        msg_timeout = rospy.Duration.from_sec(msg_timeout)
        if age > msg_timeout:
            rospy.logdebug("Ignoring old mesage with age %f" % age.to_sec())
            self.lock.release()
            return

        my_queue[msg.header.stamp] = msg
        while len(my_queue) > self.queue_size:
            del my_queue[min(my_queue)]
        if 0:
            # common is the set of timestamps that occur in all queues
            common = reduce(set.intersection, [set(q) for q in self.queues])
            for t in sorted(common):
                # msgs is list of msgs (one from each queue) with stamp t
                msgs = [q[t] for q in self.queues]
                self.signalMessage(*msgs)
                for q in self.queues:
                    del q[t]
        else:
            time_products = itertools.product(*[q.keys() for q in self.queues])
            for vv in time_products:
                if ((max(vv) - min(vv)) < self.slop):
                    msgs = [q[t] for q,t in zip(self.queues, vv)]
                    rospy.logdebug("Flushing queues. Signaling times %s" %
                                  str(vv))
                    # flush used keys
                    for q, t in zip(self.queues, vv):
                        del q[t]
                    self.signalMessage(*msgs)
                    # signal message might take arbit amount of time, we don't
                    # want old messages
                    break
        
            # clean up timeout criterian
            for q in self.queues:
                for t in q.keys():
                    if rospy.Time.now() - t > msg_timeout:
                        del q[t]

        self.lock.release()
