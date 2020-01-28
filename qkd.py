import numpy as np
import sys

from components.host import Host
from components.network import Network
from objects.qubit import Qubit
from components.logger import Logger

from math import ceil, log, sqrt
from random import randint, random, sample

Logger.DISABLED = True

def main():
    # Initialize a network
    network = Network.get_instance()

    # Define the host IDs in the network
    nodes = ['Alice', 'Bob', 'Eve']

    # Start the network with the defined hosts
    network.start(nodes)

    # Initialize the host Alice
    host_alice = Host('Alice')

    # Add a one-way connection (classical and quantum) to Bob
    host_alice.add_connection('Bob')

    # Start listening
    host_alice.start()

    host_bob = Host('Bob')
    # Bob adds his own one-way connection to Alice and Eve
    host_bob.add_connection('Alice')
    host_bob.add_connection('Eve')
    host_bob.start()

    host_eve = Host('Eve')
    host_eve.add_connection('Bob')
    host_eve.start()

    # Add the hosts to the network
    # The network is: Alice <--> Bob <--> Eve
    network.add_host(host_alice)
    network.add_host(host_bob)
    network.add_host(host_eve)


    # Run Bob and Alice
    DaemonThread(Alice_func)
    DaemonThread(Eve_func)


key_size = 128 # the size of the key in bit
secret_key = np.random.randint(2, size=key_size)

# helper function. Used get the next message with a sequence number. It ignores ACK
#                  messages and messages with other seq numbers.
def get_next_classical_message(host, receive_from_id, buffer, sequence_nr):
    buffer = buffer + host.get_classical(receive_from_id, wait=wait_time)
    msg = "ACK"
    while msg == "ACK" or (msg.split(':')[0] != ("%d" % sequence_nr)):
        if len(buffer) == 0:
            buffer = buffer + host.get_classical(receive_from_id, wait=wait_time)
        ele = buffer.pop(0)
        msg = ele["message"]
    return msg

def Alice_qkd(alice, msg_buff):
    sequence_nr = 0
    # iterate over all bits in the secret key.
    for bit in secret_key:
        ack = False
        while not ack:
            print("Alice sequence nr is %d." % sequence_nr)
            # get a random base. 0 for Z base and 1 for X base.
            base = random.randint(0, 1)

            # create qubit
            q_bit = Qubit(alice)

            # Set qubit to the bit from the secret key.
            if bit == 1:
                q_bit.X()

            # Apply basis change to the bit if necessary.
            if base == 1:
                q_bit.H()

            # Send Qubit to Bob
            alice.send_qubit(hosts['Eve'].host_id, q_bit, await_ack=True)

            # Get measured basis of Bob
            message = get_next_classical_message(alice, hosts['Eve'].host_id, msg_buff, sequence_nr)

            # Compare to send basis, if same, answer with 0 and set ack True and go to next bit,
            # otherwise, send 1 and repeat.
            if message == ("%d:%d") % (sequence_nr, base):
                ack = True
                alice.send_classical(hosts['Eve'].host_id, ("%d:0" % sequence_nr), await_ack=True)
            else:
                ack = False
                alice.send_classical(hosts['Eve'].host_id, ("%d:1" % sequence_nr), await_ack=True)

            sequence_nr += 1

def Eve_qkd(bob, msg_buff):
    eve_key = None

    sequence_nr = 0
    received_counter = 0
    key_array = []

    while received_counter < key_size:
        print("received counter is %d." % received_counter)
        print("Bob sequence nr is %d." % sequence_nr)

        # decide for a measurement base
        measurement_base = random.randint(0, 1)

        # wait for the qubit
        q_bit = bob.get_data_qubit(hosts['Alice'].host_id, wait=wait_time)
        while q_bit is None:
            q_bit = bob.get_data_qubit(hosts['Alice'].host_id, wait=wait_time)

        # measure qubit in right measurement basis
        if measurement_base == 1:
            q_bit.H()
        bit = q_bit.measure()

        # Send Alice the base in which Bob has measured
        bob.send_classical(hosts['Alice'].host_id, "%d:%d" % (sequence_nr, measurement_base) ,await_ack=True)

        # get the return message from Alice, to know if the bases have matched
        msg = get_next_classical_message(bob, hosts['Alice'].host_id, msg_buff, sequence_nr)

        # Check if the bases have matched
        if msg == ("%d:0" % sequence_nr):
            received_counter += 1
            key_array.append(bit)
        sequence_nr += 1

    eve_key = key_array

    return eve_key


# !! Warning: this Crypto algorithm is really bad!
# !! Warning: Do not use it as a real Crypto Algorithm!

# key has to be a string
def encrypt(key, text):
    encrypted_text = ""
    for char in text:
        encrypted_text += chr(ord(key)^ord(char))
    return encrypted_text

def decrypt(key, encrypted_text):
    return encrypt(key, encrypted_text)

# Test the encryption algorithm
print(decrypt('a', decrypt('a', "Encryption works!")))

# helper function, use it to make your key to a string
def key_array_to_key_string(key_array):
    key_string_binary = ''.join([str(x) for x in key_array])
    return ''.join(chr(int(''.join(x), 2)) for x in zip(*[iter(key_string_binary)]*8))

def Alice_send_message(alice, msg_buff):
    msg_to_eve = "Hi Eve, I am your biggest fangirl! Unfortunately you only exist as a computer protocol :("


    secret_key_string = key_array_to_key_string(secret_key)
    encrypted_msg_to_eve = encrypt(secret_key_string, msg_to_eve)
    alice.send_classical(hosts['Eve'].host_id, "-1:" + encrypted_msg_to_eve, await_ack=True)

def Eve_receive_message(eve, msg_buff, eve_key):
    decrypted_msg_from_alice = None


    encrypted_msg_from_alice = get_next_classical_message(eve, hosts['Alice'].host_id, msg_buff, -1)
    encrypted_msg_from_alice = encrypted_msg_from_alice.split(':')[1]
    secret_key_string = key_array_to_key_string(eve_key)
    decrypted_msg_from_alice = decrypt(secret_key_string, encrypted_msg_from_alice)

    print("Eve: Alice told me %s I am so happy!" % decrypted_msg_from_alice)


# Concatenate functions
def Alice_func(alice=hosts['Alice']):
    msg_buff = []
    Alice_qkd(alice, msg_buff)
    Alice_send_message(alice, msg_buff)

def Eve_func(eve=hosts['Eve']):
    msg_buff = []
    eve_key = Eve_qkd(eve, msg_buff)
    Eve_receive_message(eve, msg_buff, eve_key)


if __name__ == '__main__':
   main()
