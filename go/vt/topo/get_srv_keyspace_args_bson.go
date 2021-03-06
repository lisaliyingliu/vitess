// Copyright 2012, Google Inc. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

package topo

// DO NOT EDIT.
// FILE GENERATED BY BSONGEN.

import (
	"bytes"

	"github.com/youtube/vitess/go/bson"
	"github.com/youtube/vitess/go/bytes2"
)

// MarshalBson bson-encodes GetSrvKeyspaceArgs.
func (getSrvKeyspaceArgs *GetSrvKeyspaceArgs) MarshalBson(buf *bytes2.ChunkedWriter, key string) {
	bson.EncodeOptionalPrefix(buf, bson.Object, key)
	lenWriter := bson.NewLenWriter(buf)

	bson.EncodeString(buf, "Cell", getSrvKeyspaceArgs.Cell)
	bson.EncodeString(buf, "Keyspace", getSrvKeyspaceArgs.Keyspace)

	lenWriter.Close()
}

// UnmarshalBson bson-decodes into GetSrvKeyspaceArgs.
func (getSrvKeyspaceArgs *GetSrvKeyspaceArgs) UnmarshalBson(buf *bytes.Buffer, kind byte) {
	switch kind {
	case bson.EOO, bson.Object:
		// valid
	case bson.Null:
		return
	default:
		panic(bson.NewBsonError("unexpected kind %v for GetSrvKeyspaceArgs", kind))
	}
	bson.Next(buf, 4)

	for kind := bson.NextByte(buf); kind != bson.EOO; kind = bson.NextByte(buf) {
		switch bson.ReadCString(buf) {
		case "Cell":
			getSrvKeyspaceArgs.Cell = bson.DecodeString(buf, kind)
		case "Keyspace":
			getSrvKeyspaceArgs.Keyspace = bson.DecodeString(buf, kind)
		default:
			bson.Skip(buf, kind)
		}
	}
}
