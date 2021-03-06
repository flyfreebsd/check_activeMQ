#!/usr/bin/python3
# -*- coding: utf-8 -*-
import argparse
import json
import logging
import sys
from enum import Enum
from types import SimpleNamespace
from urllib.parse import urlparse

import requests
from requests import RequestException, ConnectionError, URLRequired, TooManyRedirects, Timeout


class CheckApacheMQ(object):
    """docstring for Check_Apache_MQ."""

    class ExitCode(Enum):
        """
        Enum Class to better select ExitCodes
        """
        OK = 0
        WARNING = 1
        CRITICAL = 2
        UNKNOWN = 3

    class URL:

        @property
        def host(self):
            return self.__host

        @host.setter
        def host(self, host):
            if host is not None:
                self.__host = host
            else:
                raise ValueError()

        @property
        def port(self):
            return self.__port

        @port.setter
        def port(self, port):
            if port is not None:
                self.__port = port
            else:
                raise ValueError()

        @property
        def schema(self):
            return self.__schema

        @schema.setter
        def schema(self, schema):
            if schema is not None:
                self.__schema = schema
            else:
                raise ValueError()

        @property
        def path(self):
            return self.__path

        @path.setter
        def path(self, path):
            if path is not None:
                self.__path = path
            else:
                raise ValueError()

        def __init__(self):
            self.__host = None
            self.__port = None
            self.__schema = None
            self.__path = None

        def get_url(self):

            build_url = "{}://{}:{}{}".format(self.schema, self.host, self.port, self.path)

            try:
                urlparse(build_url)
                return build_url
            except ValueError as error:
                raise ValueError("Error while checking if URL works. {}".format(build_url)) from error

    @property
    def user(self):
        return self.__user

    @user.setter
    def user(self, user):
        if user is not None:
            self.__user = user
        else:
            raise ValueError()

    @property
    def password(self):
        return self.__password

    @password.setter
    def password(self, password):
        if password is not None:
            self.__password = password
        else:
            raise ValueError()

    def __init__(self, ):
        self.__url = None
        self.__user = None
        self.__password = None

        self.url = self.URL()

        self.log = logging.getLogger('CheckApacheMQ')
        streamhandler = logging.StreamHandler(sys.stdout)
        self.log.addHandler(streamhandler)
        self.log.setLevel(logging.INFO)

    def get_health_status(self, broker_name):

        amq_path = "read/org.apache.activemq:type=Broker,brokerName={}".format(broker_name)

        data = self.query_amq(self.url.get_url() + amq_path, auth=(self.user, self.password))

        return_data = {
            "Uptime": data['value']['Uptime'],
            "BrokerVersion": data['value']['BrokerVersion'],
            "Store Usage in %": data['value']['StorePercentUsage'],
            "Memory Usage in %": data['value']['MemoryPercentUsage'],
            "Total Connections": data['value']['TotalConnectionsCount'],
            "Total Dequeue Count": data['value']['TotalDequeueCount'],
            "Total Enqueue Count": data['value']['TotalEnqueueCount']
        }

        perfdata_values = {
            "Store Usage": SimpleNamespace(value=data['value']['StorePercentUsage'],
                                           warn="",
                                           crit="",
                                           min="",
                                           max=100),
            "Memory Usage": SimpleNamespace(value=data['value']['MemoryPercentUsage'],
                                            warn="",
                                            crit="",
                                            min="",
                                            max=100),
            "Uptime": SimpleNamespace(value=data['value']['Uptime'],
                                      warn="",
                                      crit="",
                                      min="",
                                      max=""),
            "Total Dequeue Count": SimpleNamespace(value=data['value']['TotalDequeueCount'],
                                                   warn="",
                                                   crit="",
                                                   min="",
                                                   max=""),
            "Total Enqueue Count": SimpleNamespace(value=data['value']['TotalEnqueueCount'],
                                                   warn="",
                                                   crit="",
                                                   min="",
                                                   max=""),
        }

        return_string = self.build_string(return_data)

        return_string += self.build_perfdata(perfdata_values)

        self.log.info(return_string)
        sys.exit(self.ExitCode.OK.value)

    def get_queue_status(self, broker_name, queue_name, warn=None, crit=None):

        exitcode = self.ExitCode.OK.value

        amq_path = "read/org.apache.activemq:type=Broker,brokerName={},destinationType=Queue,destinationName={}".format(
            broker_name, queue_name)

        # Query values from activeMQ
        data = self.query_amq(self.url.get_url() + amq_path, auth=(self.user, self.password))

        # Building dicts to better build strings
        return_data = {
            'Queue Size': data['value']['QueueSize'],
            'Producer count': data['value']['ProducerCount'],
            'Memory Usage': data['value']['MemoryPercentUsage'],
        }

        perfdata_values = {
            "Memory Usage": SimpleNamespace(value=data['value']['MemoryUsageByteCount'],
                                            warn="",
                                            crit="",
                                            min="",
                                            max=data['value']['MemoryLimit']),
            "Queue Size": SimpleNamespace(value=data['value']['QueueSize'],
                                          warn=warn,
                                          crit=crit,
                                          min="",
                                          max=""),
            "Message Size": SimpleNamespace(value=data['value']['AverageMessageSize'],
                                            warn="",
                                            crit="",
                                            min=data['value']['MinMessageSize'],
                                            max=data['value']['MaxMessageSize']),
        }

        # checking if Queue size exceeds warn or crit values
        if crit and crit < data['value']['QueueSize']:
            return_string_begin = "Apache-MQ - CRITICAL "
            exitcode = self.ExitCode.CRITICAL.value
        elif warn and warn < data['value']['QueueSize']:
            return_string_begin = "Apache-MQ - WARNING "
            exitcode = self.ExitCode.WARNING.value
        else:
            return_string_begin = "Apache-MQ - OK \n"

        return_string = self.build_string(return_data, return_string_begin)

        return_string += self.build_perfdata(perfdata_values)

        self.log.info(return_string)
        sys.exit(exitcode)

    def build_perfdata(self, perfdata_values):
        perfdata_string = " |"

        for key, values in perfdata_values.items():
            perfdata_string += " {}={};{};{};{};{}".format(key, values.value, values.warn, values.crit, values.min,
                                                           values.max)

        return perfdata_string

    def build_string(self, string_values, string_begin="Apache-MQ - OK \n"):
        return_string = string_begin

        for key, value in string_values.items():
            return_string += " {}: {} \n".format(key, value)

        return return_string

    def query_amq(self, url, auth):
        try:
            req = requests.get(url, auth=auth)
            req.raise_for_status()
            data = json.loads(req.text)

            return data

        except RequestException as ex:
            self.log.error("Apache-MQ - CRITICAL \n Could not complete request \n {}".format(ex.message))
            sys.exit(self.ExitCode.CRITICAL.value)

        except ConnectionError as ex:
            self.log.error("Apache-MQ - CRITICAL \n Could not connect to service \n {}".format(ex.message))
            sys.exit(self.ExitCode.CRITICAL.value)

        except TooManyRedirects as ex:
            self.log.error("Apache-MQ - CRITICAL \n Too many Redirects \n {}".format(ex.message))
            sys.exit(self.ExitCode.CRITICAL.value)

        except Timeout as ex:
            self.log.error("Apache-MQ - CRITICAL \ Connection timeout \n {}".format(ex.message))
            sys.exit(self.ExitCode.CRITICAL.value)


if __name__ == '__main__':
    check = CheckApacheMQ()

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument('--host',
                        default='localhost',
                        help='Host of the Apache-MQ REST service')
    parser.add_argument('--port',
                        default='8161',
                        help='Port of the Apache-MQ REST service')
    parser.add_argument('--path',
                        default='/api/jolokia/',
                        help='URI of the Apache-MQ REST service')
    parser.add_argument('--ssl',
                        action='store_true',
                        default=False,
                        help="Flag to switch between https and http. Defaults to http")
    parser.add_argument('-u', '--username', default='admin', help='Username to be used to login')
    parser.add_argument('-p', '--password', default='admin', help='Password to be used to login')

    subparsers = parser.add_subparsers(dest='command')

    queueu_parser = subparsers.add_parser('queue')
    queueu_parser.add_argument('-b', '--broker', default='localhost',
                               help='Brokername used to determine which broker to check. \n Defaults to localhost')
    queueu_parser.add_argument('-q', '--queue', required=True, help='Queuename which is needed')
    queueu_parser.add_argument('-c', '--crit', type=int, default=500, help='Critical Value for the Queuesize')
    queueu_parser.add_argument('-w', '--warn', type=int, default=250, help='Warning Value for the Queuesize')

    health_parser = subparsers.add_parser('health')
    health_parser.add_argument('-b', '--broker', default='localhost',
                               help='Brokername used to determine which broker to check. \n Defaults to localhost')

    args = parser.parse_args()

    check.user = args.username
    check.password = args.password
    check.url.host = args.host
    check.url.port = args.port
    check.url.path = args.path

    if args.ssl:
        check.url.schema = 'https'
    else:
        check.url.schema = 'http'

    if args.command == 'queue':
        check.get_queue_status(args.broker, args.queue, args.warn, args.crit)
    elif args.command == 'health':
        check.get_health_status(args.broker)
    else:
        print("invalid call! not enough parameters")
        sys.exit(1)
