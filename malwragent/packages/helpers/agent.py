# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import time

from malwragent.packages.helpers.logger import Logger

__class_name__ = 'Agent'


class Agent(object):
    def __init__(self, name, mode, chain, interval, result_queue, logging_level=0):
        self.name = name
        self.mode = mode
        self.chain = chain
        self.interval = interval
        self.result_queue = result_queue

        self.pid = str(os.getpid())
        if hasattr(os, 'getppid'):  # only available on Unix
            self.ppid = str(os.getppid())
        # self.job_id = job_id
        self.registered = False
        self.logging_level = logging_level

        self.logger = Logger(self.name, self.logging_level)

        try:
            self.logger.log_debug('Starting new process with PID ' + self.pid)
            self.run()
        except KeyboardInterrupt:
            pass

    def run(self):

        # START inner functions

        def __convert_to_text(module_name, args):
            """convert a module name and its arguments to a text representation"""
            text = ''
            text += 'Running function '
            text += str(args['settings']['function'])
            text += ' from module '
            text += module_name
            text += ' with input <'
            text += str(args['settings']['input'])
            text += '> and args <'
            text += str(args['settings']['args'])
            text += '>'
            return text

        def __run_registration():
            """run the client registration named chain -REG-"""
            self.logger.log_debug('Chain ' + 'REG' + ' running')
            result = __run_single_chain(self.chain['REG'])
            self.logger.log_debug('Chain ' + 'REG' + ' finished')

            if result:
                self.registered = True
                msg = 'Client registration successful'

                self.logger.log_info(msg)

                """ Registration is only run once """
                del self.chain['REG']

            else:
                msg = 'Client registration failed'
                self.logger.log_critical(msg)

                # TODO[30/10/2016][bl4ckw0rm] retry registration when failed

        def __run_client():
            """run the named chain -CLIENT-"""
            while True:
                self.logger.log_info('Chain ' + 'CLIENT' + ' running')
                result = __run_single_chain(self.chain['CLIENT'])
                if result:
                    self.logger.log_info('Chain ' + 'CLIENT' + ' finished')
                else:
                    self.logger.log_critical('Chain ' + 'CLIENT' + ' finished with errors')
                    return False

                if self.interval < 1:
                    return True
                else:
                    # TODO[28/10/2016][bl4ckw0rm] random sleep
                    self.logger.log_debug('Sleeping ' + str(self.interval) + ' seconds')
                    time.sleep(self.interval)

        def __run_module(module, args=None):
            """run a module from the chain"""
            module_type = str(module.__module_type__)
            module_name = str(module.__class_name__)

            self.logger.log_debug(__convert_to_text(module_name, args))
            self.logger.log_info("Running " + module_type + " module " +
                                 str(module.__name__) + "." + module_name +
                                 " - Args: " + str(args))

            instance = getattr(module, module_name)(self.mode, args)
            # has instance a function run
            if hasattr(instance, 'run'):
                # call function run in instance
                result = getattr(instance, 'run')()
            else:
                result = False
            return result

        def __validate_result(result):
            # TODO[28/10/2016][bl4ckw0rm] type casts should be used "consistently"
            self.logger.log_debug('Result validation ' + str(type(result)) + ' ' + str(result))

            # TODO This is only very trivial
            if not result and not None:
                return False
            else:
                return True

        def __run_single_chain(chain):
            """run a named chain from the chain dict()"""
            retry_cnt = 3
            input_ = None
            timeout = 5
            run_next = None

            for item in chain:
                module, args = item
                args['settings']['input'] = input_
                ignore_output = args['settings'].get('ignore_output', False)

                try_cnt = 1
                while try_cnt <= retry_cnt:
                    output = __run_module(module, args=args)

                    if ignore_output:
                        run_next = True
                        break  # breaks out of while

                    run_next = __validate_result(output)
                    if run_next:
                        input_ = output  # output from module becomes input for next module
                        break  # breaks out of while

                    if not run_next:
                        time.sleep(timeout)
                        self.logger.log_error('Retrying %s of %s times' % (try_cnt, retry_cnt))
                        if try_cnt == retry_cnt:
                            return run_next
                        else:
                            try_cnt += 1

            return run_next

        # END inner functions

        if self.chain.get('REG', None):
            # If registration modules are included in the chain,
            # run the client only after successful registration
            __run_registration()

            if self.registered:
                self.result_queue.put(__run_client())
        else:
            # Run the client without registration
            self.result_queue.put(__run_client())
