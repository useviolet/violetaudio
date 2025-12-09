# The MIT License (MIT)
# Copyright © 2023 Yuma Rao

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import time
import asyncio
import threading
import argparse
import traceback

import bittensor as bt

from template.base.neuron import BaseNeuron
from template.utils.config import add_miner_args

from typing import Union


class BaseMinerNeuron(BaseNeuron):
    """
    Base class for Bittensor miners.
    """

    neuron_type: str = "MinerNeuron"

    @classmethod
    def add_args(cls, parser: argparse.ArgumentParser):
        super().add_args(parser)
        add_miner_args(cls, parser)

    def __init__(self, config=None):
        super().__init__(config=config)

        # Warn if allowing incoming requests from anyone.
        if not self.config.blacklist.force_validator_permit:
            bt.logging.warning(
                "You are allowing non-validators to send requests to your miner. This is a security risk."
            )
        if self.config.blacklist.allow_non_registered:
            bt.logging.warning(
                "You are allowing non-registered entities to send requests to your miner. This is a security risk."
            )
        # The axon handles request processing, allowing validators to send this miner requests.
        self.axon = bt.axon(
            wallet=self.wallet,
            config=self.config() if callable(self.config) else self.config,
        )
        
        # Ensure axon is properly configured for local and external access
        bt.logging.info(f"Axon IP: {self.axon.ip}")
        bt.logging.info(f"Axon Port: {self.axon.port}")
        bt.logging.info(f"Axon External IP: {self.axon.external_ip}")
        bt.logging.info(f"Axon External Port: {self.axon.external_port}")

        # Attach determiners which functions are called when servicing a request.
        bt.logging.info(f"Attaching forward function to miner axon.")
        self.axon.attach(
            forward_fn=self.forward,
            blacklist_fn=self.blacklist,
            priority_fn=self.priority,
        )
        
        bt.logging.info(f"Axon created: {self.axon}")

        # Instantiate runners
        self.should_exit: bool = False
        self.is_running: bool = False
        self.thread: Union[threading.Thread, None] = None
        self.lock = asyncio.Lock()

    def run(self):
        """
        Initiates and manages the main loop for the miner on the Bittensor network. The main loop handles graceful shutdown on keyboard interrupts and logs unforeseen errors.

        This function performs the following primary tasks:
        1. Check for registration on the Bittensor network.
        2. Starts the miner's axon, making it active on the network.
        3. Periodically resynchronizes with the chain; updating the metagraph with the latest network state and setting weights.

        The miner continues its operations until `should_exit` is set to True or an external interruption occurs.
        During each epoch of its operation, the miner waits for new blocks on the Bittensor network, updates its
        knowledge of the network (metagraph), and sets its weights. This process ensures the miner remains active
        and up-to-date with the network's latest state.

        Note:
            - The function leverages the global configurations set during the initialization of the miner.
            - The miner's axon serves as its interface to the Bittensor network, handling incoming and outgoing requests.

        Raises:
            KeyboardInterrupt: If the miner is stopped by a manual interruption.
            Exception: For unforeseen errors during the miner's operation, which are logged for diagnosis.
        """

        # Check that miner is registered on the network.
        self.sync()

        # Check if axon is already serving before attempting to serve
        is_already_serving = False
        try:
            if hasattr(self, 'uid') and self.uid is not None:
                # Check if the axon is already serving using metagraph
                metagraph_axon = self.metagraph.axons[self.uid]
                if metagraph_axon and hasattr(metagraph_axon, 'is_serving'):
                    if metagraph_axon.is_serving:
                        # Axon is already registered and serving
                        is_already_serving = True
                        bt.logging.info(
                            f"✅ Miner axon already serving on network: {self.config.subtensor.chain_endpoint} with netuid: {self.config.netuid}"
                        )
                        bt.logging.info(
                            f"   Current axon info: {metagraph_axon.ip}:{metagraph_axon.port}"
                        )
                elif metagraph_axon and metagraph_axon.ip != "0.0.0.0":
                    # Fallback: check if IP is set (indicates serving)
                    is_already_serving = True
                    bt.logging.info(
                        f"✅ Miner axon already serving on network: {self.config.subtensor.chain_endpoint} with netuid: {self.config.netuid}"
                    )
                    bt.logging.info(
                        f"   Current axon info: {metagraph_axon.ip}:{metagraph_axon.port}"
                    )
        except (IndexError, AttributeError, Exception) as e:
            # If we can't check, assume not serving and try to serve
            bt.logging.debug(f"Could not check serving status: {e}, will attempt to serve")

        # Serve passes the axon information to the network + netuid we are hosting on.
        # This will auto-update if the axon port of external ip have changed.
        if not is_already_serving:
            bt.logging.info(
                f"Serving miner axon {self.axon} on network: {self.config.subtensor.chain_endpoint} with netuid: {self.config.netuid}"
            )
            try:
                self.axon.serve(netuid=self.config.netuid, subtensor=self.subtensor)
                bt.logging.info("✅ Successfully served axon to network")
            except Exception as e:
                error_str = str(e)
                # Check if error is due to already serving (Custom error: 11)
                if "Custom error: 11" in error_str or "Invalid Transaction" in error_str:
                    # Check again if it's actually serving now
                    try:
                        if hasattr(self, 'uid') and self.uid is not None:
                            metagraph_axon = self.metagraph.axons[self.uid]
                            if metagraph_axon and metagraph_axon.ip != "0.0.0.0":
                                bt.logging.info(
                                    f"✅ Axon is already serving (error was expected): {metagraph_axon.ip}:{metagraph_axon.port}"
                                )
                            else:
                                bt.logging.warning(
                                    f"⚠️  Failed to serve axon (may need retry): {error_str[:100]}"
                                )
                    except Exception:
                        bt.logging.warning(
                            f"⚠️  Failed to serve axon: {error_str[:100]}"
                        )
                else:
                    # Different error, log it
                    bt.logging.error(f"❌ Failed to serve axon: {error_str[:200]}")
        else:
            # Already serving, just start the axon locally
            bt.logging.info("Axon already registered on chain, starting local server...")

        # Start  starts the miner's axon, making it active on the network.
        self.axon.start()
        
        # Verify axon is actually running and listening
        bt.logging.info(f"✅ Axon started - listening for connections")
        bt.logging.info(f"   Local: {self.axon.ip}:{self.axon.port}")
        bt.logging.info(f"   External: {self.axon.external_ip}:{self.axon.external_port}")
        bt.logging.info(f"   Axon is_serving: {self.axon.is_serving if hasattr(self.axon, 'is_serving') else 'N/A'}")

        bt.logging.info(f"Miner starting at block: {self.block}")

        # This loop maintains the miner's operations until intentionally stopped.
        try:
            while not self.should_exit:
                while (
                    self.block - self.metagraph.last_update[self.uid]
                    < self.config.neuron.epoch_length
                ):
                    # Wait before checking again.
                    time.sleep(1)

                    # Check if we should exit.
                    if self.should_exit:
                        break

                # Sync metagraph and potentially set weights.
                self.sync()
                self.step += 1

        # If someone intentionally stops the miner, it'll safely terminate operations.
        except KeyboardInterrupt:
            self.axon.stop()
            bt.logging.success("Miner killed by keyboard interrupt.")
            exit()

        # In case of unforeseen errors, the miner will log the error and continue operations.
        except Exception as e:
            bt.logging.error(traceback.format_exc())

    def run_in_background_thread(self):
        """
        Starts the miner's operations in a separate background thread.
        This is useful for non-blocking operations.
        """
        if not self.is_running:
            bt.logging.debug("Starting miner in background thread.")
            self.should_exit = False
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()
            self.is_running = True
            bt.logging.debug("Started")

    def stop_run_thread(self):
        """
        Stops the miner's operations that are running in the background thread.
        """
        if self.is_running:
            bt.logging.debug("Stopping miner in background thread.")
            self.should_exit = True
            if self.thread is not None:
                self.thread.join(5)
            self.is_running = False
            bt.logging.debug("Stopped")

    def __enter__(self):
        """
        Starts the miner's operations in a background thread upon entering the context.
        This method facilitates the use of the miner in a 'with' statement.
        """
        self.run_in_background_thread()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Stops the miner's background operations upon exiting the context.
        This method facilitates the use of the miner in a 'with' statement.

        Args:
            exc_type: The type of the exception that caused the context to be exited.
                      None if the context was exited without an exception.
            exc_value: The instance of the exception that caused the context to be exited.
                       None if the context was exited without an exception.
            traceback: A traceback object encoding the stack trace.
                       None if the context was exited without an exception.
        """
        self.stop_run_thread()

    def resync_metagraph(self):
        """Resyncs the metagraph and updates the hotkeys and moving averages based on the new metagraph."""
        bt.logging.info("resync_metagraph()")

        # Sync the metagraph.
        self.metagraph.sync(subtensor=self.subtensor)
