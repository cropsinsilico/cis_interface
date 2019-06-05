#ifndef OBJ_METASCHEMA_TYPE_H_
#define OBJ_METASCHEMA_TYPE_H_

#include "../tools.h"
#include "MetaschemaType.h"
#include "ObjDict.h"

#include "rapidjson/document.h"
#include "rapidjson/writer.h"


/*!
  @brief Class for OBJ type definition.

  The ObjMetaschemaType provides basic functionality for encoding/decoding
  Obj structures from/to JSON style strings.
 */
class ObjMetaschemaType : public MetaschemaType {
public:
  /*!
    @brief Constructor for ObjMetaschemaType.
   */
  ObjMetaschemaType() : MetaschemaType("obj") {}
  /*!
    @brief Constructor for ObjMetaschemaType from a JSON type defintion.
    @param[in] type_doc rapidjson::Value rapidjson object containing the type
    definition from a JSON encoded header.
   */
  ObjMetaschemaType(const rapidjson::Value &type_doc) : MetaschemaType(type_doc) {}
  /*!
    @brief Create a copy of the type.
    @returns pointer to new ObjMetaschemaType instance with the same data.
   */
  ObjMetaschemaType* copy() { return (new ObjMetaschemaType()); }
  /*!
    @brief Get the number of arguments expected to be filled/used by the type.
    @returns size_t Number of arguments.
   */
  virtual size_t nargs_exp() {
    return 1;
  }

  // Encoding
  /*!
    @brief Encode arguments describine an instance of this type into a JSON string.
    @param[in] writer rapidjson::Writer<rapidjson::StringBuffer> rapidjson writer.
    @param[in,out] nargs size_t * Pointer to the number of arguments contained in
    ap. On return it will be set to the number of arguments used.
    @param[in] ap va_list_t Variable number of arguments that should be encoded
    as a JSON string.
    @returns bool true if the encoding was successful, false otherwise.
   */
  bool encode_data(rapidjson::Writer<rapidjson::StringBuffer> *writer,
		   size_t *nargs, va_list_t &ap) {
    // Get argument
    obj_t p = va_arg(ap.va, obj_t);
    (*nargs)--;
    // Allocate buffer
    int buf_size = 1000;
    char *buf = (char*)malloc(buf_size);
    int msg_len = 0, ilen = 0;
    char iline[500];
    buf[0] = '\0';
    // Format header
    char header_format[500] = "# Author ygg_auto\n"
      "# Generated by yggdrasil\n";
    if (strlen(p.material) != 0) {
      sprintf(header_format + strlen(header_format), "usemtl %s\n", p.material);
    }
    ilen = (int)strlen(header_format);
    if (ilen >= (buf_size - msg_len)) {
      buf_size = buf_size + ilen;
      buf = (char*)realloc(buf, buf_size);
    }
    strcat(buf, header_format);
    msg_len = msg_len + ilen;
    // Add vertex information
    int i, j;
    for (i = 0; i < p.nvert; i++) {
      while (true) {
	if (p.vertex_colors != NULL) {
	  ilen = snprintf(buf + msg_len, buf_size - msg_len, "v %f %f %f %d %d %d\n",
			  p.vertices[i][0], p.vertices[i][1], p.vertices[i][2],
			  p.vertex_colors[i][0], p.vertex_colors[i][1], p.vertex_colors[i][2]);
	} else {
	  ilen = snprintf(buf + msg_len, buf_size - msg_len, "v %f %f %f\n",
			  p.vertices[i][0], p.vertices[i][1], p.vertices[i][2]);
	}
	if (ilen < 0) {
	  ygglog_error("ObjMetaschemaType::encode_data: Error formatting vertex %d.", i);
	  return false;
	} else if (ilen >= (buf_size - msg_len)) {
	  buf_size = buf_size + ilen + 1;
	  buf = (char*)realloc(buf, buf_size);
	} else {
	  break;
	}
      }
      msg_len = msg_len + ilen;
    }
    // Add texcoord information
    for (i = 0; i < p.ntexc; i++) {
      while (true) {
	ilen = snprintf(buf + msg_len, buf_size - msg_len, "vt %f %f\n",
			p.texcoords[i][0], p.texcoords[i][1]);
	if (ilen < 0) {
	  ygglog_error("ObjMetaschemaType::encode_data: Error formatting texcoord %d.", i);
	  return false;
	} else if (ilen >= (buf_size - msg_len)) {
	  buf_size = buf_size + ilen + 1;
	  buf = (char*)realloc(buf, buf_size);
	} else {
	  break;
	}
      }
      msg_len = msg_len + ilen;
    }
    // Add normal information
    for (i = 0; i < p.nnorm; i++) {
      while (true) {
	ilen = snprintf(buf + msg_len, buf_size - msg_len, "vn %f %f %f\n",
			p.normals[i][0], p.normals[i][1], p.normals[i][2]);
	if (ilen < 0) {
	  ygglog_error("ObjMetaschemaType::encode_data: Error formatting normal %d.", i);
	  return false;
	} else if (ilen >= (buf_size - msg_len)) {
	  buf_size = buf_size + ilen + 1;
	  buf = (char*)realloc(buf, buf_size);
	} else {
	  break;
	}
      }
      msg_len = msg_len + ilen;
    }
    // Add face information
    for (i = 0; i < p.nface; i++) {
      char ival[10];
      sprintf(iline, "f");
      for (j = 0; j < 3; j++) {
	sprintf(ival, " %d", p.faces[i][j] + 1);
	strcat(iline, ival);
	strcat(iline, "/");
	if (p.face_texcoords[i][j] >= 0) {
	  sprintf(ival, "%d", p.face_texcoords[i][j] + 1);
	  strcat(iline, ival);
	}
	strcat(iline, "/");
	if (p.face_normals[i][j] >= 0) {
	  sprintf(ival, "%d", p.face_normals[i][j] + 1);
	  strcat(iline, ival);
	}
      }
      while (true) {
	ilen = snprintf(buf + msg_len, buf_size - msg_len, "%s\n", iline);
	if (ilen < 0) {
	  ygglog_error("ObjMetaschemaType::encode_data: Error formatting line face %d.", i);
	  return false;
	} else if (ilen >= (buf_size - msg_len)) {
	  buf_size = buf_size + ilen + 1;
	  buf = (char*)realloc(buf, buf_size);
	} else {
	  break;
	}
      }
      msg_len = msg_len + ilen;
    }
    ygglog_info("writing:\n%s",buf);
    buf[msg_len] = '\0';
    writer->String(buf, msg_len);
    return true;
  }

  // Decoded
  /*!
    @brief Decode variables from a JSON string.
    @param[in] data rapidjson::Value Reference to entry in JSON string.
    @param[in] allow_realloc int If 1, the passed variables will be reallocated
    to contain the deserialized data.
    @param[in,out] nargs size_t Number of arguments contained in ap. On return,
    the number of arguments assigned from the deserialized data will be assigned
    to this address.
    @param[out] ap va_list_t Reference to variable argument list containing
    address where deserialized data should be assigned.
    @returns bool true if the data was successfully decoded, false otherwise.
   */
  bool decode_data(rapidjson::Value &data, const int allow_realloc,
		   size_t *nargs, va_list_t &ap) {
    if (!(data.IsString()))
      ygglog_throw_error("ObjMetaschemaType::decode_data: Data is not a string.");
    // Get input data
    const char *buf = data.GetString();
    size_t buf_siz = data.GetStringLength();
    // Get output argument
    obj_t *p;
    obj_t **pp;
    if (allow_realloc) {
      pp = va_arg(ap.va, obj_t**);
      p = (obj_t*)realloc(*pp, sizeof(obj_t));
      if (p == NULL)
	ygglog_throw_error("ObjMetaschemaType::decode_data: could not realloc pointer.");
      *pp = p;
      *p = init_obj();
    } else {
      p = va_arg(ap.va, obj_t*);
    }
    (*nargs)--;
    // Process buffer
    int out = 1;
    int do_colors = 0;
    size_t *sind = NULL;
    size_t *eind = NULL;
    int nlines = 0;
    int j;
    int nvert = 0, nface = 0, ntexc = 0, nnorm = 0, nmatl = 0;
    // Counts
    int n_re_vert = 7;
    int n_re_face = 3*3 + 1;
    int n_re_texc = 3;
    int n_re_norm = 4;
    int n_re_matl = 2;
    char re_vert[100] = "v ([^ \n]+) ([^ \n]+) ([^ \n]+) ([^ \n]+) ([^ \n]+) ([^ \n]+)";
    char re_face[100] = "f ([^ \n/]*)/([^ \n/]*)/([^ \n/]*) "
      "([^ \n/]*)/([^ \n/]*)/([^ \n/]*) "
      "([^ \n/]*)/([^ \n/]*)/([^ \n/]*)";
    char re_texc[100] = "vt ([^ \n]+) ([^ \n]+)";
    char re_norm[100] = "vn ([^ \n]+) ([^ \n]+) ([^ \n]+)";
    char re_matl[100] = "usemtl ([^\n]+)";
    nvert = count_matches(re_vert, buf);
    if (nvert != 0) {
      do_colors = 1;
    } else {
      strncpy(re_vert, "v ([^ \n]+) ([^ \n]+) ([^ \n]+)", 100);
      n_re_vert = 4;
      nvert = count_matches(re_vert, buf);
    }
    nface = count_matches(re_face, buf);
    ntexc = count_matches(re_texc, buf);
    nnorm = count_matches(re_norm, buf);
    nmatl = count_matches(re_matl, buf);
    ygglog_debug("deserialize_obj: expecting %d verts, %d faces, %d texcoords, %d normals",
		 nvert, nface, ntexc, nnorm);
    // Allocate
    if (out > 0) {
      int ret = alloc_obj(p, nvert, nface, ntexc, nnorm, do_colors);
      if (ret < 0) {
	ygglog_error("deserialize_obj: Error allocating obj structure.");
	out = -1;
      }
    }
    // Locate lines
    int cvert = 0, cface = 0, ctexc = 0, cnorm = 0, cmatl = 0;
    size_t cur_pos = 0;
    char iline[500];
    size_t iline_siz = 0;
    size_t sind_line, eind_line;
    if (out > 0) {
      /* char ival[10]; */
      /* size_t ival_siz = 0; */
      while (cur_pos < buf_siz) {
	ygglog_debug("deserialize_obj: Starting position %d/%d",
		     cur_pos, buf_siz);
	int n_sub_matches = find_match("([^\n]*)\n", buf + cur_pos,
				       &sind_line, &eind_line);
	if (n_sub_matches == 0) {
	  ygglog_debug("deserialize_obj: End of file.");
	  sind_line = 0;
	  eind_line = buf_siz - cur_pos;
	}
	iline_siz = eind_line - sind_line;
	memcpy(iline, buf + cur_pos, iline_siz);
	iline[iline_siz] = '\0';
	ygglog_debug("deserialize_obj: iline = %s", iline);
	// Match line
	if (find_matches("#[^\n]*", iline, &sind, &eind) == 1) {
	  // Comment
	  ygglog_debug("deserialize_obj: Comment");
	} else if (find_matches(re_matl, iline, &sind, &eind) == n_re_matl) {
	  // Material
	  ygglog_debug("deserialize_obj: Material");
	  int matl_size = (int)(eind[1] - sind[1]);
	  memcpy(p->material, iline+sind[1], matl_size);
	  p->material[matl_size] = '\0';
	  cmatl++;
	} else if (find_matches(re_vert, iline, &sind, &eind) == n_re_vert) {
	  // Vertex
	  ygglog_debug("deserialize_obj: Vertex");
	  for (j = 0; j < 3; j++) {
	    p->vertices[cvert][j] = (float)atof(iline + sind[j+1]);
	  }
	  if (do_colors) {
	    for (j = 0; j < 3; j++) {
	      p->vertex_colors[cvert][j] = atoi(iline + sind[j+4]);
	    }
	  }
	  cvert++;
	} else if (find_matches(re_norm, iline, &sind, &eind) == n_re_norm) {
	  // Normals
	  ygglog_debug("deserialize_obj: Normals");
	  for (j = 0; j < 3; j++) {
	    p->normals[cnorm][j] = (float)atof(iline + sind[j+1]);
	  }
	  cnorm++;
	} else if (find_matches(re_texc, iline, &sind, &eind) == n_re_texc) {
	  // Texcoords
	  ygglog_debug("deserialize_obj: Texcoords");
	  for (j = 0; j < 2; j++) {
	    p->texcoords[ctexc][j] = (float)atof(iline + sind[j+1]);
	  }
	  ctexc++;
	} else if (find_matches(re_face, iline, &sind, &eind) == n_re_face) {
	  // Face
	  //int n_sub_matches2 = 
	  find_matches(re_face, iline, &sind, &eind);
	  ygglog_debug("deserialize_obj: Face");
	  for (j = 0; j < 3; j++) {
	    p->faces[cface][j] = atoi(iline + sind[3*j+1]) - 1;
	    if ((eind[3*j+2] - sind[3*j+2]) == 0)
	      p->face_texcoords[cface][j] = -1;
	    else
	      p->face_texcoords[cface][j] = atoi(iline + sind[3*j+2]) - 1;
	    if ((eind[3*j+3] - sind[3*j+3]) == 0)
	      p->face_normals[cface][j] = -1;
	    else
	      p->face_normals[cface][j] = atoi(iline + sind[3*j+3]) - 1;
	  }
	  cface++;
	} else if (find_matches("\n+", iline, &sind, &eind) == 1) {
	  // Empty line
	  ygglog_debug("deserialize_obj: Empty line");
	} else {
	  ygglog_error("deserialize_obj: Could not match line: %s", iline);
	  out = -1;
	  break;
	}
	nlines++;
	cur_pos = cur_pos + eind_line;
	ygglog_debug("deserialize_obj: Advancing to position %d/%d",
		     cur_pos, buf_siz);
      }
    }
    if (out > 0) {
      if (cvert != nvert) {
	ygglog_error("deserialize_obj: Found %d verts, expected %d.", cvert, nvert);
	out = -1;
      }
      if (cface != nface) {
	ygglog_error("deserialize_obj: Found %d faces, expected %d.", cface, nface);
	out = -1;
      }
      if (ctexc != ntexc) {
	ygglog_error("deserialize_obj: Found %d texcs, expected %d.", ctexc, ntexc);
	out = -1;
      }
      if (cnorm != nnorm) {
	ygglog_error("deserialize_obj: Found %d norms, expected %d.", cnorm, nnorm);
	out = -1;
      }
      if (cmatl != nmatl) {
	ygglog_error("deserialize_obj: Found %d materials, expected %d.", cmatl, nmatl);
	out = -1;
      }
    }
    // Return
    if (sind != NULL) free(sind); 
    if (eind != NULL) free(eind);
    if (out < 0) {
      free_obj(p);
      return false;
    } else {
      return true;
    }
  }

};

#endif /*OBJ_METASCHEMA_TYPE_H_*/
// Local Variables:
// mode: c++
// End: