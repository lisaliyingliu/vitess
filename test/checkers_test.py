#!/usr/bin/env python
 # -*- coding: utf-8 -*-
import json
import logging
import optparse
import os
import sys
import tempfile
import unittest
import warnings

import tablet
import utils

from checkers import checker
from checkers import write_configuration


# Dropping a table inexplicably produces a warning despite
# the "IF EXISTS" clause. Squelch these warnings.
warnings.simplefilter("ignore")


skip_teardown = False

# I need this mostly for mysql
destination_tablet = tablet.Tablet(62344, 6700, 3700)
source_tablets = [tablet.Tablet(62044, 6701, 3701),
                  tablet.Tablet(41983, 6702, 3702)]
tablets = [destination_tablet] + source_tablets

db_configuration = {
  "sources": [t.mysql_connection_parameters("test_checkers%i" % i) for i, t in enumerate(source_tablets)],
}

def setUpModule():
  utils.wait_procs([t.start_mysql() for t in tablets])

def tearDownModule():
  global skip_teardown
  if skip_teardown:
    return

  utils.wait_procs([t.teardown_mysql() for t in tablets], raise_on_error=False)
  utils.kill_sub_processes()
  for t in tablets:
    t.remove_tree()


class TestCheckersBase(unittest.TestCase):
  keyrange = {"end": 900}

  def make_checker(self, **kwargs):
    default = {'keyrange': TestCheckers.keyrange,
               'batch_count': 20,
               'logging_level': logging.WARNING,
               'directory': tempfile.mkdtemp()}
    default.update(kwargs)
    source_addresses = ['vt_dba@localhost:%s/test_checkers%s?unix_socket=%s' % (s.mysql_port, i, s.mysql_connection_parameters('test_checkers')['unix_socket'])
                        for i, s in enumerate(source_tablets)]
    destination_socket = destination_tablet.mysql_connection_parameters('test_checkers')['unix_socket']
    return checker.Checker('vt_dba@localhost/test_checkers?unix_socket=%s' % destination_socket, source_addresses, 'test', **default)

class TestCheckers(TestCheckersBase):

  @classmethod
  def setUpClass(cls):
    config = dict(db_configuration)
    cls.configuration = config

  def setUp(self):
    create_table = "create table test (pk1 bigint, pk2 bigint, pk3 bigint, keyspace_id bigint, msg varchar(64), primary key (pk1, pk2, pk3)) Engine=InnoDB"
    destination_tablet.create_db("test_checkers")
    destination_tablet.mquery("test_checkers", create_table, True)
    for i, t in enumerate(source_tablets):
      t.create_db("test_checkers%s" % i)
      t.mquery("test_checkers%s" % i, create_table, True)

    destination_queries = []
    source_queries = [[] for t in source_tablets]
    for i in range(1, 400):
      query = "insert into test (pk1, pk2, pk3, msg, keyspace_id) values (%s, %s, %s, 'message %s', %s)" % (i/100+1, i/10+1, i, i, i)
      destination_queries.append(query)
      source_queries[i % 2].append(query)
    for i in range(1100, 1110):
      query = "insert into test (pk1, pk2, pk3, msg, keyspace_id) values (%s, %s, %s, 'message %s', %s)" % (i/100+1, i/10+1, i, i, i)
      source_queries[0].append(query)

    destination_tablet.mquery("test_checkers", destination_queries, write=True)
    for i, (tablet, queries) in enumerate(zip(source_tablets, source_queries)):
      tablet.mquery("test_checkers%s" % i, queries, write=True)
    self.c = self.make_checker()

  def tearDown(self):
    destination_tablet.mquery("test_checkers", "drop table test", True)
    for i, t in enumerate(source_tablets):
      t.mquery("test_checkers%s" % i, "drop table test", True)

  def query_all(self, sql, write=False):
    return [t.mquery("test_checkers", sql, write=write) for t in tablets]


  def test_ok(self):
    self.c._run()

  def test_different_value(self):
    destination_tablet.mquery("test_checkers", "update test set msg='something else' where pk2 = 29 and pk3 = 280 and pk1 = 3", write=True)
    with self.assertRaises(checker.Mismatch):
      self.c._run()

  def test_additional_value(self):
    destination_tablet.mquery("test_checkers", "insert into test (pk1, pk2, pk3) values (1, 1, 900)", write=True)
    with self.assertRaises(checker.Mismatch):
      self.c._run()

  def test_batch_size(self):
    c = self.make_checker(batch_count=0)
    c.table_data['avg_row_length'] = 1024
    c.calculate_batch_size()
    self.assertEqual(c.batch_size, 16)


class TestDifferentEncoding(TestCheckersBase):
  @classmethod
  def setUpClass(cls):
    config = dict(db_configuration)
    cls.configuration = config

  def setUp(self):
    create_table = "create table test (pk1 bigint, pk2 bigint, pk3 bigint, keyspace_id bigint, msg varchar(64), primary key (pk1, pk2, pk3)) Engine=InnoDB"
    destination_tablet.create_db("test_checkers")
    destination_tablet.mquery("test_checkers", create_table + "default character set = utf8", True)
    for i, t in enumerate(source_tablets):
      t.create_db("test_checkers%s" % i)
      t.mquery("test_checkers%s" % i, create_table + "default character set = latin2", True)

    destination_queries = []
    source_queries = [[] for t in source_tablets]
    source_connections = [t.connect('test_checkers%s' % i) for i, t in enumerate(source_tablets)]
    for c, _ in source_connections:
      c.set_character_set('latin2')
      c.begin()
    for i in range(1, 400):
      query = u"insert into test (pk1, pk2, pk3, keyspace_id, msg) values (%s, %s, %s, %s, '\xb1 %s')" % (i/100+1, i/10+1, i, i, i)
      destination_queries.append(query)
      #source_queries[i % 2].append(query.encode('utf-8').decode('iso-8859-2'))
      source_connections[i % 2][1].execute(query.encode('utf-8').decode('iso-8859-2'))
    for c, _ in source_connections:
      c.commit()

    destination_tablet.mquery("test_checkers", destination_queries, write=True)
    self.c = self.make_checker()

  def test_problem(self):
    with self.assertRaises(checker.Mismatch):
      self.c._run()


def main():
  parser = optparse.OptionParser(usage="usage: %prog [options] [test_names]")
  parser.add_option('--skip-teardown', action='store_true')
  parser.add_option('--teardown', action='store_true')
  parser.add_option("-q", "--quiet", action="store_const", const=0, dest="verbose", default=1)
  parser.add_option("-v", "--verbose", action="store_const", const=2, dest="verbose", default=1)
  parser.add_option("--no-build", action="store_true")

  (options, args) = parser.parse_args()

  utils.options = options
  global skip_teardown
  skip_teardown = options.skip_teardown
  if options.teardown:
    tearDownModule()
    sys.exit()
  unittest.main(argv=sys.argv[:1] + ['-f'])


if __name__ == '__main__':
  main()