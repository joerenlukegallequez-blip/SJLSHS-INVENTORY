"""
╔══════════════════════════════════════════════════════════════╗
║   SAN JOSE LITEX SENIOR HIGH SCHOOL                         ║
║   School Inventory Management System                         ║
║   Single-File Version — Python + SQL + HTML                  ║
║                                                              ║
║   HOW TO RUN:                                                ║
║     1. pip install flask                                     ║
║     2. Place download.png inside an "images" folder          ║
║        (same directory as app.py)                            ║
║     3. python app.py                                         ║
║     4. Open browser → http://127.0.0.1:5000                  ║
║                                                              ║
║   LOGIN CREDENTIALS:                                         ║
║     Username : ADMIN                                         ║
║     Password : 123                                           ║
╚══════════════════════════════════════════════════════════════╝
"""

from flask import Flask, request, jsonify, session, redirect, url_for, send_from_directory
import sqlite3, os
from datetime import datetime
from functools import wraps
from io import BytesIO
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT

app = Flask(__name__)
app.secret_key = "SJL_SHS_SECRET_KEY_2025"
DB     = os.path.join(os.path.dirname(__file__), "sjl_inventory.db")
IMGDIR = os.path.join(os.path.dirname(__file__), "images")

ADMIN_USERNAME = "ADMIN"
ADMIN_PASSWORD = "123"


# ══════════════════════════════════════════════════════════════
#  SERVE LOCAL IMAGES  (images/download.png, etc.)
# ══════════════════════════════════════════════════════════════
@app.route("/images/<path:filename>")
def serve_image(filename):
    return send_from_directory(IMGDIR, filename)


# ══════════════════════════════════════════════════════════════
#  AUTH DECORATOR
# ══════════════════════════════════════════════════════════════
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


# ══════════════════════════════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════════════════════════════
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db(); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        color TEXT NOT NULL DEFAULT '#2563EB')""")
    c.execute("""CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, category_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 0, unit TEXT NOT NULL DEFAULT 'pcs',
        location TEXT, condition TEXT NOT NULL DEFAULT 'Good',
        min_stock INTEGER NOT NULL DEFAULT 5, description TEXT,
        date_added TEXT NOT NULL, last_updated TEXT NOT NULL,
        FOREIGN KEY (category_id) REFERENCES categories(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL, action TEXT NOT NULL,
        quantity INTEGER NOT NULL, performed_by TEXT, notes TEXT,
        timestamp TEXT NOT NULL, FOREIGN KEY (item_id) REFERENCES items(id))""")
    # ── Wipe all existing items & transaction history on startup ──
    c.execute("DELETE FROM transactions")
    c.execute("DELETE FROM items")
    c.execute("DELETE FROM sqlite_sequence WHERE name='items' OR name='transactions'")
    seed_cats = [
        ("Laboratory Equipment","#1D4ED8"),("Office Supplies","#2563EB"),
        ("Sports Equipment","#3B82F6"),("Technology / ICT","#1E40AF"),
        ("Furniture","#60A5FA"),("Textbooks & Materials","#93C5FD")]
    c.executemany("INSERT OR IGNORE INTO categories (name,color) VALUES (?,?)", seed_cats)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 1=Laboratory Equipment, 2=Office Supplies, 3=Sports Equipment
    # 4=Technology/ICT, 5=Furniture, 6=Textbooks & Materials
    sample_items = [
        ("Microscope",       1, 10, "units", "Science Lab Room 1",  "Good", 3,  "Binocular compound microscope"),
        ("Bond Paper A4",    2, 20, "reams", "Supply Room",         "Good", 5,  "80gsm white paper"),
        ("Basketball",       3,  8, "pcs",   "Gymnasium",           "Good", 2,  "Official size 7"),
        ("Desktop Computer", 4, 15, "units", "Computer Laboratory", "Good", 5,  "Core i5, 8GB RAM, 256GB SSD"),
        ("Student Chair",    5,120, "pcs",   "Various Classrooms",  "Good", 20, "Standard monobloc chair"),
    ]
    for row in sample_items:
        c.execute("""INSERT INTO items
            (name,category_id,quantity,unit,location,condition,min_stock,description,date_added,last_updated)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", (*row, now, now))
    conn.commit(); conn.close()


# ══════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ══════════════════════════════════════════════════════════════
@app.route("/login", methods=["GET"])
def login_page():
    if session.get("logged_in"):
        return redirect(url_for("index"))
    return LOGIN_PAGE

@app.route("/login", methods=["POST"])
def do_login():
    data = request.json
    u = data.get("username","").strip().upper()
    p = data.get("password","").strip()
    if u == ADMIN_USERNAME and p == ADMIN_PASSWORD:
        session["logged_in"] = True
        session["username"]  = ADMIN_USERNAME
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Invalid username or password."})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


# ══════════════════════════════════════════════════════════════
#  PROTECTED APP ROUTES
# ══════════════════════════════════════════════════════════════
@app.route("/")
@login_required
def index():
    return HTML_PAGE

@app.route("/api/stats")
@login_required
def api_stats():
    conn = get_db(); c = conn.cursor()
    total = c.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    qty   = c.execute("SELECT COALESCE(SUM(quantity),0) FROM items").fetchone()[0]
    cats  = c.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    recnt = c.execute("""SELECT t.action,t.quantity,t.timestamp,i.name
        FROM transactions t JOIN items i ON t.item_id=i.id
        ORDER BY t.timestamp DESC LIMIT 6""").fetchall()
    conn.close()
    return jsonify({"total_items":total,"total_quantity":qty,
        "categories":cats,"recent_transactions":[dict(r) for r in recnt]})

@app.route("/api/items", methods=["GET"])
@login_required
def api_items_get():
    conn = get_db()
    search = request.args.get("search","")
    cat    = request.args.get("category","")
    cond   = request.args.get("condition","")
    sql    = """SELECT i.*,c.name AS category_name,c.color AS category_color
                FROM items i JOIN categories c ON i.category_id=c.id WHERE 1=1"""
    params = []
    if search:
        sql += " AND (i.name LIKE ? OR i.description LIKE ? OR i.location LIKE ?)"; params += [f"%{search}%"]*3
    if cat:   sql += " AND i.category_id=?"; params.append(cat)
    if cond:  sql += " AND i.condition=?";   params.append(cond)
    sql += " ORDER BY i.name"
    rows = conn.execute(sql, params).fetchall(); conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/items", methods=["POST"])
@login_required
def api_items_post():
    d = request.json; now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db(); c = conn.cursor()
    c.execute("""INSERT INTO items
        (name,category_id,quantity,unit,location,condition,min_stock,description,date_added,last_updated)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (d["name"],d["category_id"],d["quantity"],d.get("unit","pcs"),
         d.get("location",""),d.get("condition","Good"),d.get("min_stock",5),
         d.get("description",""),now,now))
    iid = c.lastrowid
    c.execute("INSERT INTO transactions (item_id,action,quantity,performed_by,notes,timestamp) VALUES (?,?,?,?,?,?)",
        (iid,"Added",d["quantity"],d.get("performed_by","Admin"),"Initial stock",now))
    conn.commit(); conn.close()
    return jsonify({"success":True,"id":iid})

@app.route("/api/items/<int:iid>", methods=["GET"])
@login_required
def api_item_get(iid):
    conn = get_db()
    row = conn.execute("""SELECT i.*,c.name AS category_name
        FROM items i JOIN categories c ON i.category_id=c.id WHERE i.id=?""",(iid,)).fetchone()
    conn.close()
    return jsonify(dict(row)) if row else (jsonify({"error":"Not found"}),404)

@app.route("/api/items/<int:iid>", methods=["PUT"])
@login_required
def api_item_put(iid):
    d = request.json; now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    conn.execute("""UPDATE items SET name=?,category_id=?,quantity=?,unit=?,location=?,
        condition=?,min_stock=?,description=?,last_updated=? WHERE id=?""",
        (d["name"],d["category_id"],d["quantity"],d.get("unit","pcs"),
         d.get("location",""),d.get("condition","Good"),d.get("min_stock",5),
         d.get("description",""),now,iid))
    conn.execute("INSERT INTO transactions (item_id,action,quantity,performed_by,notes,timestamp) VALUES (?,?,?,?,?,?)",
        (iid,"Updated",d["quantity"],d.get("performed_by","Admin"),d.get("notes","Item updated"),now))
    conn.commit(); conn.close()
    return jsonify({"success":True})

@app.route("/api/items/<int:iid>", methods=["DELETE"])
@login_required
def api_item_delete(iid):
    conn = get_db()
    conn.execute("DELETE FROM transactions WHERE item_id=?",(iid,))
    conn.execute("DELETE FROM items WHERE id=?",(iid,))
    conn.commit(); conn.close()
    return jsonify({"success":True})

@app.route("/api/items/<int:iid>/adjust", methods=["POST"])
@login_required
def api_adjust(iid):
    d = request.json; action = d.get("action","add"); qty = int(d.get("quantity",0))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db(); c = conn.cursor()
    cur = c.execute("SELECT quantity FROM items WHERE id=?",(iid,)).fetchone()
    if not cur: conn.close(); return jsonify({"error":"Not found"}),404
    new_qty = cur[0]+qty if action=="add" else max(0,cur[0]-qty)
    c.execute("UPDATE items SET quantity=?,last_updated=? WHERE id=?",(new_qty,now,iid))
    c.execute("INSERT INTO transactions (item_id,action,quantity,performed_by,notes,timestamp) VALUES (?,?,?,?,?,?)",
        (iid,"Stock In" if action=="add" else "Stock Out",qty,d.get("performed_by","Admin"),d.get("notes",""),now))
    conn.commit(); conn.close()
    return jsonify({"success":True,"new_quantity":new_qty})

@app.route("/api/categories")
@login_required
def api_categories():
    conn = get_db()
    rows = conn.execute("SELECT * FROM categories ORDER BY name").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/transactions")
@login_required
def api_transactions():
    conn = get_db()
    rows = conn.execute("""SELECT t.*,i.name AS item_name
        FROM transactions t JOIN items i ON t.item_id=i.id
        ORDER BY t.timestamp DESC LIMIT 100""").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ══════════════════════════════════════════════════════════════
#  PDF EXPORT
# ══════════════════════════════════════════════════════════════
@app.route("/api/export/pdf")
@login_required
def export_pdf():
    from flask import make_response
    conn = get_db()
    items = conn.execute("""
        SELECT i.name, c.name AS category, i.quantity, i.unit,
               i.location, i.condition, i.min_stock, i.description, i.last_updated
        FROM items i JOIN categories c ON i.category_id = c.id
        ORDER BY i.name""").fetchall()
    conn.close()

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.8*cm, bottomMargin=1.8*cm)

    from reportlab.platypus import Image as RLImage
    from reportlab.lib.units import inch

    now_str = datetime.now().strftime("%B %d, %Y  %I:%M %p")

    # ── Direct paragraph styles (no table nesting) ──
    _base = getSampleStyleSheet()["Normal"]
    st_title  = ParagraphStyle("pdftitle",  parent=_base, fontName="Helvetica-Bold",
                               fontSize=20, leading=26, textColor=colors.HexColor("#1D4ED8"),
                               alignment=TA_CENTER, spaceAfter=8)
    st_sub    = ParagraphStyle("pdfsub",    parent=_base, fontName="Helvetica-Bold",
                               fontSize=14, leading=18, textColor=colors.HexColor("#1E3A5F"),
                               alignment=TA_CENTER, spaceAfter=6)
    st_gen    = ParagraphStyle("pdfgen",    parent=_base, fontName="Helvetica",
                               fontSize=11, leading=15, textColor=colors.HexColor("#3B5A8A"),
                               alignment=TA_CENTER, spaceAfter=4)
    footer_style = ParagraphStyle("pdffooter", parent=_base, fontName="Helvetica",
                                  fontSize=8, textColor=colors.HexColor("#6B8FC4"),
                                  alignment=TA_CENTER)

    # ── Logo left + Title right layout ──
    logo_path = os.path.join(IMGDIR, "download.png")

    title_p = Paragraph("SAN JOSE LITEX SENIOR HIGH SCHOOL", st_title)
    sub_p   = Paragraph("School Inventory Report", st_sub)
    gen_p   = Paragraph(f"Generated: {now_str}  &nbsp;|&nbsp;  Total Items: {len(items)}", st_gen)

    if os.path.isfile(logo_path):
        logo_el = RLImage(logo_path, width=2.4*cm, height=2.4*cm)
        # Side-by-side: logo left, text right — paragraphs go directly in cell (styles preserved)
        page_w = landscape(A4)[0] - 3*cm   # usable width
        hdr_tbl = Table(
            [[logo_el, [title_p, sub_p, gen_p]]],
            colWidths=[2.8*cm, page_w - 2.8*cm]
        )
        hdr_tbl.setStyle(TableStyle([
            ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
            ("ALIGN",        (0,0), (0,0),   "CENTER"),
            ("LEFTPADDING",  (0,0), (-1,-1), 0),
            ("RIGHTPADDING", (0,0), (-1,-1), 0),
            ("TOPPADDING",   (0,0), (-1,-1), 0),
            ("BOTTOMPADDING",(0,0), (-1,-1), 0),
        ]))
        story = [
            hdr_tbl,
            Spacer(1, 0.3*cm),
            HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563EB")),
            Spacer(1, 0.35*cm),
        ]
    else:
        story = [
            title_p, sub_p, gen_p,
            Spacer(1, 0.3*cm),
            HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563EB")),
            Spacer(1, 0.35*cm),
        ]

    # Table header
    header = ["#", "Item Name", "Category", "Qty", "Unit", "Location", "Condition", "Min Stock", "Last Updated"]
    col_w  = [1*cm, 6*cm, 4.2*cm, 1.6*cm, 1.6*cm, 4.5*cm, 2.2*cm, 2*cm, 3.8*cm]

    data = [header]
    for i, row in enumerate(items, 1):
        data.append([
            str(i),
            row["name"],
            row["category"],
            str(row["quantity"]),
            row["unit"] or "",
            row["location"] or "—",
            row["condition"],
            str(row["min_stock"]),
            (row["last_updated"] or "")[:10],
        ])

    BLUE   = colors.HexColor("#2563EB")
    LBLUE  = colors.HexColor("#DBEAFE")
    LGRAY  = colors.HexColor("#F0F7FF")
    BLACK  = colors.HexColor("#1E3A5F")
    GREEN  = colors.HexColor("#10B981")
    YELLOW = colors.HexColor("#F59E0B")
    RED    = colors.HexColor("#EF4444")

    t = Table(data, colWidths=col_w, repeatRows=1)
    ts = TableStyle([
        # Header
        ("BACKGROUND",   (0,0), (-1,0), BLUE),
        ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,0), 8.5),
        ("ALIGN",        (0,0), (-1,0), "CENTER"),
        ("VALIGN",       (0,0), (-1,-1),"MIDDLE"),
        ("TOPPADDING",   (0,0), (-1,0), 8),
        ("BOTTOMPADDING",(0,0), (-1,0), 8),
        # Body
        ("FONTNAME",     (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE",     (0,1), (-1,-1), 8),
        ("TOPPADDING",   (0,1), (-1,-1), 6),
        ("BOTTOMPADDING",(0,1), (-1,-1), 6),
        ("TEXTCOLOR",    (0,1), (-1,-1), BLACK),
        ("ALIGN",        (0,1), (0,-1), "CENTER"),   # # col
        ("ALIGN",        (3,1), (3,-1), "CENTER"),   # Qty
        ("ALIGN",        (7,1), (7,-1), "CENTER"),   # Min Stock
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, LGRAY]),
        ("GRID",         (0,0), (-1,-1), 0.4, colors.HexColor("#BFDBFE")),
        ("LINEBELOW",    (0,0), (-1,0),  1.2, BLUE),
        ("ROUNDEDCORNERS",[3,3,3,3]),
    ])
    # Condition colour coding
    for i, row in enumerate(items, 1):
        cond = row["condition"]
        col = GREEN if cond == "Good" else (YELLOW if cond == "Fair" else RED)
        ts.add("TEXTCOLOR", (6,i), (6,i), col)
        ts.add("FONTNAME",  (6,i), (6,i), "Helvetica-Bold")
    t.setStyle(ts)

    story.append(t)
    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#BFDBFE")))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph("San Jose Litex Senior High School  ·  Lot 1 Block 9 Litex Village Montalban Rizal  ·  Region 4A CALABARZON  ·  Est. 2026", footer_style))

    doc.build(story)
    buf.seek(0)

    fname = f"SJL_Inventory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    resp = make_response(buf.read())
    resp.headers["Content-Type"]        = "application/pdf"
    resp.headers["Content-Disposition"] = f"attachment; filename={fname}"
    return resp


# ══════════════════════════════════════════════════════════════
#  LOGIN PAGE
# ══════════════════════════════════════════════════════════════
LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>SJL-SHS — Admin Login</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&display=swap" rel="stylesheet"/>
<style>
:root{
  --card:#FFFFFF;--card2:#F0F7FF;
  --border:#BFDBFE;--border2:#93C5FD;
  --blue:#2563EB;--blue2:#1D4ED8;--blue-light:#DBEAFE;
  --red:#EF4444;--t1:#1E3A5F;--t2:#3B5A8A;--t3:#93A8C4;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;}
body{
  font-family:'Outfit',sans-serif;
  background:linear-gradient(145deg,#1D4ED8 0%,#3B82F6 55%,#60A5FA 100%);
  color:var(--t1);display:flex;align-items:center;justify-content:center;
  min-height:100vh;overflow:hidden;
}
body::before{
  content:'';position:fixed;inset:0;
  background-image:linear-gradient(rgba(255,255,255,.06) 1px,transparent 1px),
    linear-gradient(90deg,rgba(255,255,255,.06) 1px,transparent 1px);
  background-size:48px 48px;pointer-events:none;z-index:0;
}
body::after{
  content:'';position:fixed;width:700px;height:700px;border-radius:50%;
  background:radial-gradient(circle,rgba(255,255,255,.08) 0%,transparent 70%);
  top:50%;left:50%;transform:translate(-50%,-50%);pointer-events:none;z-index:0;
}

/* ── Wrap ── */
.login-wrap{position:relative;z-index:1;width:100%;max-width:430px;padding:20px;}

/* ── School badge ── */
.school-badge{display:flex;flex-direction:column;align-items:center;margin-bottom:26px;gap:14px;}
.badge-logo-ring{
  width:100px;height:100px;border-radius:50%;
  background:rgba(255,255,255,.15);border:3px solid rgba(255,255,255,.35);
  display:flex;align-items:center;justify-content:center;
  box-shadow:0 0 0 6px rgba(255,255,255,.08),0 12px 40px rgba(0,0,0,.22);
  animation:pulse 3s ease-in-out infinite;overflow:hidden;
}
@keyframes pulse{
  0%,100%{box-shadow:0 0 0 6px rgba(255,255,255,.08),0 12px 40px rgba(0,0,0,.22);}
  50%{box-shadow:0 0 0 14px rgba(255,255,255,.04),0 12px 48px rgba(0,0,0,.28);}
}
.badge-logo-ring img{
  width:100%;height:100%;object-fit:cover;display:block;
}
/* Fallback text if image fails */
.badge-logo-ring .fallback-text{
  font-size:26px;font-weight:900;color:#fff;letter-spacing:-.5px;
  display:none;
}
.badge-logo-ring img.errored{display:none;}
.badge-logo-ring img.errored ~ .fallback-text{display:block;}

.badge-title h1{font-size:19px;font-weight:800;color:#fff;text-align:center;margin-bottom:4px;line-height:1.25;}
.badge-title p{font-size:12px;color:rgba(255,255,255,.72);text-align:center;letter-spacing:.03em;}

/* ── Card ── */
.login-card{
  background:var(--card);border:1px solid rgba(255,255,255,.4);
  border-radius:22px;padding:32px;box-shadow:0 16px 56px rgba(0,0,0,.2);
}
.login-header{margin-bottom:20px;text-align:center;}
.login-header h2{font-size:20px;font-weight:700;color:var(--t1);margin-bottom:4px;}
.login-header p{font-size:12.5px;color:var(--t3);}
.admin-strip{
  display:flex;align-items:center;justify-content:center;gap:8px;
  background:var(--blue-light);border:1px solid var(--border2);
  border-radius:10px;padding:9px 14px;margin-bottom:22px;
}
.admin-strip span{font-size:12px;font-weight:700;color:var(--blue);letter-spacing:.06em;}

/* ── Form ── */
.fg{display:flex;flex-direction:column;gap:6px;margin-bottom:16px;}
label{font-size:11.5px;font-weight:700;color:var(--t2);letter-spacing:.05em;text-transform:uppercase;}
.input-wrap{position:relative;}
.input-icon{
  position:absolute;left:13px;top:50%;transform:translateY(-50%);
  font-size:15px;color:var(--t3);pointer-events:none;line-height:1;
}
.input-wrap input{
  width:100%;background:var(--card2);border:1px solid var(--border);
  color:var(--t1);font-family:'Outfit',sans-serif;font-size:14px;
  padding:11px 13px 11px 40px;border-radius:10px;outline:none;
  transition:border-color .18s,box-shadow .18s;
}
.input-wrap input:focus{border-color:var(--blue);box-shadow:0 0 0 3px rgba(37,99,235,.12);}
.input-wrap input::placeholder{color:var(--t3);}
.eye-btn{
  position:absolute;right:12px;top:50%;transform:translateY(-50%);
  background:none;border:none;cursor:pointer;font-size:15px;color:var(--t3);
  padding:2px;transition:color .15s;line-height:1;
}
.eye-btn:hover{color:var(--t2);}

/* ── Error ── */
.err-box{
  display:none;align-items:center;gap:8px;
  background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.25);
  border-radius:9px;padding:10px 13px;margin-bottom:16px;
  font-size:12.5px;color:var(--red);
}
.err-box.show{display:flex;animation:shake .4s ease;}
@keyframes shake{0%,100%{transform:translateX(0)}20%{transform:translateX(-8px)}40%{transform:translateX(8px)}60%{transform:translateX(-5px)}80%{transform:translateX(5px)}}

/* ── Button ── */
.login-btn{
  width:100%;padding:13px;border-radius:11px;border:none;
  background:linear-gradient(135deg,var(--blue) 0%,var(--blue2) 100%);
  color:#fff;font-family:'Outfit',sans-serif;font-size:14px;font-weight:700;
  cursor:pointer;box-shadow:0 6px 20px rgba(37,99,235,.35);
  transition:all .18s;letter-spacing:.03em;
  display:flex;align-items:center;justify-content:center;gap:8px;
}
.login-btn:hover{background:linear-gradient(135deg,#3B82F6 0%,var(--blue) 100%);box-shadow:0 8px 28px rgba(37,99,235,.5);transform:translateY(-1px);}
.login-btn:active{transform:translateY(0);}
.login-btn:disabled{opacity:.6;cursor:not-allowed;transform:none;}
.spinner{width:16px;height:16px;border:2px solid rgba(255,255,255,.3);border-top-color:#fff;border-radius:50%;animation:spin .6s linear infinite;display:none;}
@keyframes spin{to{transform:rotate(360deg)}}

/* ── Footer ── */
.login-footer{text-align:center;margin-top:18px;font-size:11px;color:rgba(255,255,255,.6);line-height:1.7;}
.login-footer b{color:rgba(255,255,255,.85);}
</style>
</head>
<body>

<div class="login-wrap">

  <!-- School seal -->
  <div class="school-badge">
    <div class="badge-logo-ring">
      <img
        src="/images/download.png"
        alt="San Jose Litex SHS"
        onerror="this.classList.add('errored')"
      />
      <span class="fallback-text">SJL</span>
    </div>
    <div class="badge-title">
      <h1>San Jose Litex Senior High School</h1>
      <p>Inventory Management System</p>
    </div>
  </div>

  <!-- Login card -->
  <div class="login-card">
    <div class="login-header">
      <h2>🔐 Admin Login</h2>
      <p>Enter your credentials to continue</p>
    </div>
    <div class="admin-strip">
      <span>🛡️</span><span>ADMINISTRATOR ACCESS ONLY</span>
    </div>
    <div class="err-box" id="err-box">❌ <span id="err-msg"></span></div>
    <div class="fg">
      <label>Username</label>
      <div class="input-wrap">
        <span class="input-icon">👤</span>
        <input type="text" id="inp-user" placeholder="Enter username"
               autocomplete="username" oninput="clearErr()" onkeydown="enterKey(event)"/>
      </div>
    </div>
    <div class="fg">
      <label>Password</label>
      <div class="input-wrap">
        <span class="input-icon">🔒</span>
        <input type="password" id="inp-pass" placeholder="Enter password"
               autocomplete="current-password" oninput="clearErr()" onkeydown="enterKey(event)"/>
        <button class="eye-btn" type="button" onclick="togglePw()" id="eye-btn">👁️</button>
      </div>
    </div>
    <button class="login-btn" id="login-btn" onclick="doLogin()">
      <div class="spinner" id="spinner"></div>
      <span id="btn-text">Login to System</span>
    </button>
  </div>

  <div class="login-footer">
    🏫 <b>Lot 1 Block 9 Litex Village Montalban Rizal</b><br/>
    Region 4A CALABARZON &nbsp;·&nbsp; Est. 2026
  </div>
</div>

<script>
let pwVisible=false;
function togglePw(){
  pwVisible=!pwVisible;
  document.getElementById('inp-pass').type=pwVisible?'text':'password';
  document.getElementById('eye-btn').textContent=pwVisible?'🙈':'👁️';
}
function enterKey(e){if(e.key==='Enter')doLogin();}
function clearErr(){document.getElementById('err-box').classList.remove('show');}
function showErr(msg){
  const b=document.getElementById('err-box');
  document.getElementById('err-msg').textContent=msg;
  b.classList.remove('show'); void b.offsetWidth; b.classList.add('show');
}
async function doLogin(){
  const user=document.getElementById('inp-user').value.trim();
  const pass=document.getElementById('inp-pass').value.trim();
  if(!user){showErr('Please enter your username.');return;}
  if(!pass){showErr('Please enter your password.');return;}
  const btn=document.getElementById('login-btn');
  const sp=document.getElementById('spinner');
  const bt=document.getElementById('btn-text');
  btn.disabled=true; sp.style.display='block'; bt.textContent='Signing in…';
  try{
    const res=await fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:user,password:pass})});
    const data=await res.json();
    if(data.success){bt.textContent='✅ Success!';setTimeout(()=>{window.location.href='/';},600);}
    else{showErr(data.error||'Invalid credentials.');btn.disabled=false;sp.style.display='none';bt.textContent='Login to System';}
  }catch(e){showErr('Connection error. Please try again.');btn.disabled=false;sp.style.display='none';bt.textContent='Login to System';}
}
window.onload=()=>document.getElementById('inp-user').focus();
</script>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════
#  MAIN APP HTML
# ══════════════════════════════════════════════════════════════
HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>SJL-SHS Inventory System</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet"/>
<style>
:root{
  --sidebar:#FFFFFF;--card:#FFFFFF;--card2:#F0F7FF;
  --border:#BFDBFE;--border2:#93C5FD;
  --blue:#2563EB;--blue2:#1D4ED8;--blue-light:#EFF6FF;--blue-mid:#DBEAFE;
  --green:#10B981;--red:#EF4444;--yellow:#F59E0B;
  --t1:#1E3A5F;--t2:#3B5A8A;--t3:#6B8FC4;
  --r:14px;--s:0 4px 20px rgba(0,0,0,.08);
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{
  font-family:'Outfit',sans-serif;
  background:linear-gradient(145deg,#1D4ED8 0%,#3B82F6 55%,#60A5FA 100%);
  background-attachment:fixed;color:var(--t1);min-height:100vh;overflow-x:hidden;
}
body::before{
  content:'';position:fixed;inset:0;
  background-image:linear-gradient(rgba(255,255,255,.05) 1px,transparent 1px),
    linear-gradient(90deg,rgba(255,255,255,.05) 1px,transparent 1px);
  background-size:48px 48px;pointer-events:none;z-index:0;
}
/* ── Sidebar ── */
.sidebar{position:fixed;left:0;top:0;height:100vh;width:252px;background:var(--sidebar);border-right:1px solid var(--border2);display:flex;flex-direction:column;z-index:100;box-shadow:3px 0 20px rgba(0,0,0,.12);}
.logo-wrap{padding:16px 18px;border-bottom:1px solid var(--border);}
.logo-inner{display:flex;align-items:center;gap:12px;}
.logo-img{width:44px;height:44px;border-radius:10px;object-fit:cover;flex-shrink:0;box-shadow:0 2px 8px rgba(37,99,235,.25);}
.logo-hex{width:44px;height:44px;border-radius:10px;flex-shrink:0;background:linear-gradient(135deg,var(--blue) 0%,var(--blue2) 100%);display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:900;color:#fff;box-shadow:0 4px 14px rgba(37,99,235,.3);}
.logo-txt{display:flex;flex-direction:column;gap:2px;}
.logo-txt b{font-size:14px;font-weight:800;color:var(--blue);letter-spacing:.03em;}
.logo-txt small{font-size:10.5px;color:var(--t3);line-height:1.35;}
.nav-group{padding:16px 14px 4px;font-size:10px;font-weight:700;color:var(--t3);letter-spacing:.12em;text-transform:uppercase;}
.nav-item{display:flex;align-items:center;gap:11px;padding:10px 14px;margin:2px 8px;border-radius:10px;cursor:pointer;transition:all .15s;font-size:13.5px;font-weight:500;color:var(--t2);position:relative;user-select:none;}
.nav-item:hover{background:var(--blue-mid);color:var(--blue);}
.nav-item.active{background:linear-gradient(135deg,rgba(37,99,235,.13),rgba(37,99,235,.06));color:var(--blue);border:1px solid rgba(37,99,235,.2);}
.nav-item.active::before{content:'';position:absolute;left:-8px;top:50%;transform:translateY(-50%);width:3px;height:55%;background:var(--blue);border-radius:4px;}
.nav-icon{font-size:17px;width:20px;text-align:center;flex-shrink:0;}
.sidebar-user{padding:14px 16px;border-top:1px solid var(--border);display:flex;align-items:center;gap:10px;margin-top:auto;}
.user-avatar{width:34px;height:34px;border-radius:9px;flex-shrink:0;background:linear-gradient(135deg,var(--blue),var(--blue2));display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:900;color:#fff;}
.user-info{flex:1;min-width:0;}
.user-name{font-size:13px;font-weight:700;color:var(--blue);}
.user-role{font-size:10.5px;color:var(--t3);}
.logout-btn{background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.2);color:var(--red);font-size:11px;font-weight:600;padding:5px 9px;border-radius:7px;cursor:pointer;transition:all .15s;white-space:nowrap;font-family:'Outfit',sans-serif;}
.logout-btn:hover{background:rgba(239,68,68,.16);}
.sidebar-foot{padding:10px 18px 14px;font-size:11px;color:var(--t3);text-align:center;line-height:1.7;}
.sidebar-foot span{color:var(--blue);font-weight:600;}
/* ── Main / Topbar ── */
.main{margin-left:252px;min-height:100vh;position:relative;z-index:1;}
.topbar{display:flex;align-items:center;justify-content:space-between;padding:15px 26px;background:var(--blue2);border-bottom:1px solid rgba(255,255,255,.15);position:sticky;top:0;z-index:50;box-shadow:0 2px 16px rgba(0,0,0,.18);}
.topbar-left{display:flex;align-items:center;gap:13px;}
.page-tag{font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--blue2);background:#fff;padding:4px 11px;border-radius:6px;}
.topbar-title{font-size:17px;font-weight:700;color:#fff;}
.topbar-right{display:flex;align-items:center;gap:10px;}
.clock{font-family:'JetBrains Mono',monospace;font-size:12px;color:rgba(255,255,255,.85);background:rgba(255,255,255,.12);padding:7px 13px;border-radius:8px;border:1px solid rgba(255,255,255,.2);letter-spacing:.05em;}
.date-tag{font-size:11px;color:rgba(255,255,255,.7);padding:7px 8px;}
.admin-pill{display:flex;align-items:center;gap:7px;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.25);padding:6px 13px;border-radius:20px;font-size:12px;font-weight:700;color:#fff;}
/* ── Buttons ── */
.btn{display:inline-flex;align-items:center;gap:7px;padding:9px 18px;border-radius:9px;font-family:inherit;font-size:13px;font-weight:600;cursor:pointer;border:none;transition:all .16s;text-decoration:none;}
.btn-blue{background:var(--blue);color:#fff;box-shadow:0 4px 14px rgba(37,99,235,.3);}
.btn-blue:hover{background:var(--blue2);box-shadow:0 6px 20px rgba(37,99,235,.45);}
.btn-ghost{background:var(--card2);color:var(--t1);border:1px solid var(--border2);}
.btn-ghost:hover{border-color:var(--blue);color:var(--blue);}
.btn-red{background:rgba(239,68,68,.08);color:var(--red);border:1px solid rgba(239,68,68,.2);}
.btn-red:hover{background:rgba(239,68,68,.16);}
.btn-green{background:rgba(16,185,129,.08);color:var(--green);border:1px solid rgba(16,185,129,.2);}
.btn-green:hover{background:rgba(16,185,129,.16);}
.btn-outline{background:#fff;color:var(--blue);border:1px solid var(--border2);}
.btn-outline:hover{background:var(--blue-mid);}
.btn-sm{padding:6px 12px;font-size:11.5px;}
/* ── Content / Pages ── */
.content{padding:24px 26px;}
.page{display:none;}
.page.active{display:block;animation:pageIn .28s ease;}
@keyframes pageIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
/* ── Banner ── */
.banner{border-radius:var(--r);padding:24px 28px;margin-bottom:22px;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.25);backdrop-filter:blur(8px);display:flex;align-items:center;gap:22px;position:relative;overflow:hidden;}
.banner::after{content:'';position:absolute;right:-50px;top:-50px;width:240px;height:240px;border-radius:50%;background:radial-gradient(circle,rgba(255,255,255,.1),transparent 70%);pointer-events:none;}
.banner-seal{font-size:52px;filter:drop-shadow(0 4px 10px rgba(0,0,0,.15));}
.banner-text h1{font-size:21px;font-weight:800;color:#fff;margin-bottom:4px;}
.banner-text p{font-size:13px;color:rgba(255,255,255,.78);}
.banner-text small{font-size:11px;color:rgba(255,255,255,.55);}
.banner-chips{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap;}
.chip{font-size:11px;font-weight:600;padding:4px 10px;border-radius:20px;background:rgba(255,255,255,.18);color:#fff;border:1px solid rgba(255,255,255,.25);}
/* ── Card ── */
.card{background:var(--card);border:1px solid var(--border2);border-radius:var(--r);overflow:hidden;box-shadow:var(--s);}
.card-head{display:flex;align-items:center;justify-content:space-between;padding:15px 20px;border-bottom:1px solid var(--border);}
.card-head-left{display:flex;align-items:center;gap:10px;}
.card-title{font-size:14.5px;font-weight:700;color:var(--t1);}
.card-count{font-size:11px;font-weight:600;padding:3px 9px;border-radius:20px;background:var(--blue-mid);color:var(--blue);}
/* ── Filters ── */
.filters{display:flex;gap:10px;padding:13px 18px;border-bottom:1px solid var(--border);flex-wrap:wrap;align-items:center;}
.search-wrap{position:relative;flex:1;min-width:200px;}
.search-icon{position:absolute;left:11px;top:50%;transform:translateY(-50%);font-size:14px;color:var(--t3);pointer-events:none;display:flex;align-items:center;line-height:1;z-index:1;}
.search-wrap input{width:100%;padding-left:34px !important;}
/* ── Inputs ── */
input[type="text"],input[type="number"],select,textarea{background:var(--card2);border:1px solid var(--border2);color:var(--t1);font-family:inherit;font-size:13px;padding:8px 13px;border-radius:9px;outline:none;transition:border-color .16s,box-shadow .16s;}input[type="number"]::-webkit-outer-spin-button,input[type="number"]::-webkit-inner-spin-button{-webkit-appearance:none;margin:0;}input[type="number"]{-moz-appearance:textfield;}
input:focus,select:focus,textarea:focus{border-color:var(--blue);box-shadow:0 0 0 3px rgba(37,99,235,.1);}
select option{background:#fff;}
label{font-size:12px;font-weight:600;color:var(--t2);letter-spacing:.04em;}
/* ── Table ── */
.table-wrap{overflow-x:auto;}
table{width:100%;border-collapse:collapse;}
thead tr{background:var(--blue-mid);}
th{text-align:left;padding:11px 16px;font-size:10.5px;font-weight:700;color:var(--blue);letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid var(--border2);white-space:nowrap;}
td{padding:12px 16px;font-size:13px;border-bottom:1px solid var(--border);vertical-align:middle;color:var(--t1);}
tr:last-child td{border-bottom:none;}
tr:hover td{background:#F5F9FF;}
.empty{text-align:center;color:var(--t3);padding:40px!important;font-size:14px;}
/* ── Badges ── */
.b{display:inline-block;padding:3px 9px;border-radius:20px;font-size:11px;font-weight:600;white-space:nowrap;}
.b-good{background:rgba(16,185,129,.1);color:var(--green);}
.b-fair{background:rgba(245,158,11,.1);color:var(--yellow);}
.b-poor{background:rgba(239,68,68,.1);color:var(--red);}
.cat-chip{display:inline-block;padding:4px 10px;border-radius:20px;font-size:11px;font-weight:600;min-width:130px;text-align:center;white-space:nowrap;}
.qty-val{font-size:15px;font-weight:700;color:var(--t1);}
/* ── Modals ── */
.overlay{display:none;position:fixed;inset:0;background:rgba(10,30,70,.5);backdrop-filter:blur(8px);z-index:500;align-items:center;justify-content:center;padding:20px;}
.overlay.open{display:flex;}
.modal{background:var(--card);border:1px solid var(--border2);border-radius:18px;width:540px;max-width:100%;max-height:90vh;overflow-y:auto;box-shadow:0 24px 64px rgba(0,0,0,.2);animation:modalIn .22s ease;}
.modal-sm{width:400px;}
@keyframes modalIn{from{opacity:0;transform:scale(.93)}to{opacity:1;transform:none}}
.modal-head{display:flex;align-items:center;justify-content:space-between;padding:18px 22px;border-bottom:1px solid var(--border);background:var(--blue2);border-radius:18px 18px 0 0;}
.modal-head h2{font-size:16px;font-weight:700;color:#fff;}
.modal-head h2 span{font-size:13px;font-weight:400;color:rgba(255,255,255,.6);margin-left:6px;}
.x-btn{background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.25);color:#fff;font-size:17px;width:30px;height:30px;border-radius:7px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .15s;}
.x-btn:hover{background:rgba(239,68,68,.25);border-color:rgba(239,68,68,.4);}
.modal-body{padding:22px;}
.fg{display:flex;flex-direction:column;gap:6px;margin-bottom:14px;}
.fg.half{display:grid;grid-template-columns:1fr 1fr;gap:14px;}
.fg.half .fg{margin-bottom:0;}
.fg input,.fg select,.fg textarea{width:100%;}
textarea{resize:vertical;min-height:72px;}
.modal-foot{display:flex;justify-content:flex-end;gap:10px;padding:15px 22px;border-top:1px solid var(--border);}
/* ── Toasts ── */
.toasts{position:fixed;bottom:22px;right:22px;z-index:999;display:flex;flex-direction:column;gap:8px;}
.toast{display:flex;align-items:center;gap:12px;background:var(--card);border:1px solid var(--border2);padding:12px 16px;border-radius:11px;min-width:270px;box-shadow:0 8px 24px rgba(0,0,0,.12);animation:toastIn .28s ease;font-size:13px;font-weight:500;color:var(--t1);}
.toast.ok{border-left:3px solid var(--green);}
.toast.err{border-left:3px solid var(--red);}
.toast.inf{border-left:3px solid var(--blue);}
@keyframes toastIn{from{opacity:0;transform:translateX(24px)}to{opacity:1;transform:none}}
/* ── Activity Feed ── */
.feed-item{display:flex;align-items:flex-start;gap:12px;padding:12px 0;border-bottom:1px solid var(--border);}
.feed-item:last-child{border-bottom:none;}
.feed-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0;margin-top:3px;}
.feed-dot.in{background:var(--green);box-shadow:0 0 6px rgba(16,185,129,.4);}
.feed-dot.out{background:var(--red);}
.feed-dot.upd{background:var(--yellow);}
.feed-dot.add{background:var(--blue);}
.feed-info{flex:1;}
.feed-name{font-size:13px;font-weight:600;color:var(--t1);}
.feed-meta{font-size:11px;color:var(--t3);margin-top:2px;}
.feed-qty{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;}
/* ── Dashboard grid ── */
.dash-grid{display:grid;grid-template-columns:1fr 360px;gap:18px;}
@media(max-width:1060px){.dash-grid{grid-template-columns:1fr;}}
@media(max-width:580px){.banner{flex-direction:column;text-align:center;}}
</style>
</head>
<body>

<!-- ══ SIDEBAR ══ -->
<aside class="sidebar">
  <div class="logo-wrap">
    <div class="logo-inner">
      <img class="logo-img" src="/images/download.png" alt="SJLSHS"
           onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"/>
      <div class="logo-hex" style="display:none">S</div>
      <div class="logo-txt">
        <b>SJLSHS</b>
        <small>San Jose-Litex<br/>Senior High School</small>
      </div>
    </div>
  </div>

  <div class="nav-group">Navigation</div>
  <div class="nav-item active" onclick="goto('dashboard',this)">
    <span class="nav-icon">📊</span> Dashboard
  </div>
  <div class="nav-item" onclick="goto('inventory',this)">
    <span class="nav-icon">📦</span> Inventory
  </div>
  <div class="nav-item" onclick="goto('transactions',this)">
    <span class="nav-icon">📋</span> Transactions
  </div>
  <div class="nav-group">Quick Actions</div>
  <div class="nav-item" onclick="openAdd()">
    <span class="nav-icon">➕</span> Add New Item
  </div>

  <div class="sidebar-user">
    <div class="user-avatar">A</div>
    <div class="user-info">
      <div class="user-name">ADMIN</div>
      <div class="user-role">Administrator</div>
    </div>
    <button class="logout-btn" onclick="confirmLogout()">Logout</button>
  </div>
  <div class="sidebar-foot">Inventory System v1.0<br/><span>San Jose Litex SHS</span></div>
</aside>

<!-- ══ MAIN ══ -->
<main class="main">
  <div class="topbar">
    <div class="topbar-left">
      <span class="page-tag" id="page-tag">DASHBOARD</span>
      <span class="topbar-title" id="page-title">Overview</span>
    </div>
    <div class="topbar-right">
      <div class="admin-pill">🛡️ ADMIN</div>
      <span class="date-tag" id="date-disp"></span>
      <span class="clock" id="clock">00:00:00</span>
    </div>
  </div>

  <div class="content">

  <!-- DASHBOARD -->
  <div class="page active" id="pg-dashboard">
    <div class="banner">
      <div class="banner-seal">🏫</div>
      <div class="banner-text">
        <h1>San Jose-Litex Senior High School</h1>
        <p>School ID: 342566</p>
        <small>Lot 1 Block Litex Village San Jose Montalban Rizal</small>
        <div class="banner-chips">
          <span class="chip">📦 Inventory</span>
          <span class="chip">🔄 Live Tracking</span>
          <span class="chip">📋 Audit Log</span>
          <span class="chip">🔐 Admin Access</span>
        </div>
      </div>
    </div>
    <div class="dash-grid">
      <div class="card">
        <div class="card-head">
          <div class="card-head-left">
            <span class="card-title">📋 Inventory Overview</span>
            <span class="card-count" id="dash-count">— items</span>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Item</th>
                <th style="text-align:center">Category</th>
                <th style="text-align:center">Qty</th>
                <th>Location</th>
                <th>Condition</th>
              </tr>
            </thead>
            <tbody id="dash-tbody"><tr><td colspan="5" class="empty">Loading…</td></tr></tbody>
          </table>
        </div>
      </div>
      <div class="card">
        <div class="card-head"><span class="card-title">🔄 Recent Activity</span></div>
        <div style="padding:8px 16px" id="feed-wrap"><p class="empty">Loading…</p></div>
      </div>
    </div>
  </div>

  <!-- INVENTORY -->
  <div class="page" id="pg-inventory">
    <div class="card">
      <div class="card-head">
        <div class="card-head-left">
          <span class="card-title">📦 Full Inventory</span>
          <span class="card-count" id="inv-count">—</span>
        </div>
        <div style="display:flex;gap:8px"><button class="btn btn-ghost btn-sm" onclick="exportPDF()" id="pdf-btn">📄 Export PDF</button><button class="btn btn-blue btn-sm" onclick="openAdd()">＋ Add Item</button></div>
      </div>
      <div class="filters">
        <div class="search-wrap">
          <span class="search-icon">🔍</span>
          <input type="text" id="inv-q" placeholder="Search name, location, description…" oninput="loadInventory()"/>
        </div>
        <select id="inv-cat" onchange="loadInventory()"><option value="">All Categories</option></select>
        <select id="inv-cond" onchange="loadInventory()">
          <option value="">All Conditions</option>
          <option>Good</option><option>Fair</option><option>Poor</option>
        </select>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Item Name</th>
              <th style="text-align:center">Category</th>
              <th style="text-align:center">Quantity</th>
              <th>Unit</th>
              <th>Location</th>
              <th>Condition</th>
              <th>Last Updated</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody id="inv-tbody"><tr><td colspan="9" class="empty">Loading…</td></tr></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- TRANSACTIONS -->
  <div class="page" id="pg-transactions">
    <div class="card">
      <div class="card-head">
        <span class="card-title">📋 Transaction Log</span>
        <span style="font-size:12px;color:var(--t3)">Last 100 entries</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>Timestamp</th><th>Item</th><th>Action</th><th>Quantity</th><th>Performed By</th><th>Notes</th></tr>
          </thead>
          <tbody id="txn-tbody"><tr><td colspan="6" class="empty">Loading…</td></tr></tbody>
        </table>
      </div>
    </div>
  </div>

  </div>
</main>

<!-- ADD / EDIT MODAL -->
<div class="overlay" id="item-modal">
  <div class="modal">
    <div class="modal-head">
      <h2 id="modal-ttl">Add New Item <span id="modal-sub"></span></h2>
      <button class="x-btn" onclick="closeModal('#item-modal')">✕</button>
    </div>
    <div class="modal-body">
      <div class="fg"><label>Item Name *</label><input type="text" id="f-name" placeholder="e.g. Compound Microscope"/></div>
      <div class="fg half">
        <div class="fg"><label>Category *</label><select id="f-cat"></select></div>
        <div class="fg"><label>Condition</label><select id="f-cond"><option>Good</option><option>Fair</option><option>Poor</option></select></div>
      </div>
      <div class="fg half">
        <div class="fg"><label>Quantity *</label><input type="number" id="f-qty" min="0" placeholder="0"/></div>
        <div class="fg"><label>Unit</label><select id="f-unit"><option>pcs</option><option>units</option><option>copies</option><option>boxes</option><option>reams</option><option>sets</option><option>pairs</option></select></div>
      </div>
      <div class="fg half">
        <div class="fg"><label>Min Stock Threshold</label><input type="number" id="f-min" min="0" placeholder="5"/></div>
        <div class="fg"><label>Location</label><input type="text" id="f-loc" placeholder="e.g. Science Lab Room 1"/></div>
      </div>
      <div class="fg"><label>Description / Notes</label><textarea id="f-desc" placeholder="Optional details…"></textarea></div>
    </div>
    <div class="modal-foot">
      <button class="btn btn-ghost" onclick="closeModal('#item-modal')">Cancel</button>
      <button class="btn btn-blue" onclick="saveItem()">💾 Save Item</button>
    </div>
  </div>
</div>

<!-- STOCK ADJUST MODAL -->
<div class="overlay" id="adj-modal">
  <div class="modal modal-sm">
    <div class="modal-head">
      <h2>± Adjust Stock <span id="adj-sub"></span></h2>
      <button class="x-btn" onclick="closeModal('#adj-modal')">✕</button>
    </div>
    <div class="modal-body">
      <div class="fg"><label>Action</label><select id="adj-action"><option value="add">📥 Stock In — Add quantity</option><option value="remove">📤 Stock Out — Remove quantity</option></select></div>
      <div class="fg"><label>Quantity</label><input type="number" id="adj-qty" min="1" value="1"/></div>
      <div class="fg"><label>Performed By</label><input type="text" id="adj-by" placeholder="Name of teacher/admin"/></div>
      <div class="fg"><label>Notes / Reason</label><textarea id="adj-notes" placeholder="e.g. Purchased from budget 2025…"></textarea></div>
    </div>
    <div class="modal-foot">
      <button class="btn btn-ghost" onclick="closeModal('#adj-modal')">Cancel</button>
      <button class="btn btn-blue" onclick="doAdjust()">✅ Confirm</button>
    </div>
  </div>
</div>

<div class="toasts" id="toasts"></div>

<script>
let curPage='dashboard',editId=null,adjId=null,cats=[];

function confirmLogout(){
  if(confirm('Are you sure you want to logout?')) window.location.href='/logout';
}
function tick(){
  const n=new Date();
  document.getElementById('clock').textContent=n.toLocaleTimeString('en-PH',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
  document.getElementById('date-disp').textContent=n.toLocaleDateString('en-PH',{weekday:'short',year:'numeric',month:'short',day:'numeric'});
}
setInterval(tick,1000); tick();

function goto(name,el){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
  document.getElementById('pg-'+name).classList.add('active');
  if(el) el.classList.add('active');
  curPage=name;
  const T={dashboard:'Overview',inventory:'All Items',transactions:'Audit Log'};
  const G={dashboard:'DASHBOARD',inventory:'INVENTORY',transactions:'TRANSACTIONS'};
  document.getElementById('page-title').textContent=T[name]||name;
  document.getElementById('page-tag').textContent=G[name]||name.toUpperCase();
  if(name==='dashboard')    loadDash();
  if(name==='inventory')    loadInventory();
  if(name==='transactions') loadTxn();
}

async function api(url,method='GET',body=null){
  const o={method,headers:{'Content-Type':'application/json'}};
  if(body) o.body=JSON.stringify(body);
  const r=await fetch(url,o);
  if(r.status===401){window.location.href='/login';return;}
  return r.json();
}

async function loadCats(){
  cats=await api('/api/categories');
  const opts=cats.map(c=>`<option value="${c.id}">${c.name}</option>`).join('');
  document.getElementById('f-cat').innerHTML=opts;
  document.getElementById('inv-cat').innerHTML='<option value="">All Categories</option>'+opts;
}

async function loadDash(){
  const [st,items]=await Promise.all([api('/api/stats'),api('/api/items')]);
  document.getElementById('dash-count').textContent=items.length+' items';
  const tb=document.getElementById('dash-tbody');
  tb.innerHTML=items.slice(0,20).map(it=>`
    <tr>
      <td><strong>${it.name}</strong></td>
      <td style="text-align:center"><span class="cat-chip" style="background:${it.category_color}18;color:${it.category_color}">${it.category_name}</span></td>
      <td style="text-align:center"><span class="qty-val">${it.quantity} ${it.unit}</span></td>
      <td style="color:var(--t2);font-size:12px">${it.location||'—'}</td>
      <td><span class="b b-${it.condition.toLowerCase()}">${it.condition}</span></td>
    </tr>`).join('')||'<tr><td colspan="5" class="empty">No items found.</td></tr>';
  const fw=document.getElementById('feed-wrap');
  if(!st.recent_transactions.length){fw.innerHTML='<p class="empty">No activity yet.</p>';return;}
  const dc={'Stock In':'in','Stock Out':'out','Updated':'upd','Added':'add'};
  fw.innerHTML=st.recent_transactions.map(t=>`
    <div class="feed-item">
      <span class="feed-dot ${dc[t.action]||'add'}"></span>
      <div class="feed-info">
        <div class="feed-name">${t.name}</div>
        <div class="feed-meta">${t.action} &bull; ${fmtDt(t.timestamp)}</div>
      </div>
      <div class="feed-qty" style="color:${t.action==='Stock Out'?'var(--red)':'var(--green)'}">
        ${t.action==='Stock Out'?'−':'+'}${t.quantity}
      </div>
    </div>`).join('');
}

async function loadInventory(){
  const q=document.getElementById('inv-q').value;
  const cat=document.getElementById('inv-cat').value;
  const cond=document.getElementById('inv-cond').value;
  const items=await api(`/api/items?search=${encodeURIComponent(q)}&category=${cat}&condition=${cond}`);
  document.getElementById('inv-count').textContent=items.length+' item(s)';
  const tb=document.getElementById('inv-tbody');
  tb.innerHTML=items.map((it,i)=>`
    <tr>
      <td style="color:var(--t3);font-size:12px;font-family:'JetBrains Mono',monospace">${String(i+1).padStart(2,'0')}</td>
      <td>
        <div style="font-weight:600">${it.name}</div>
        ${it.description?`<div style="font-size:11px;color:var(--t3);margin-top:2px">${it.description}</div>`:''}
      </td>
      <td style="text-align:center"><span class="cat-chip" style="background:${it.category_color}18;color:${it.category_color}">${it.category_name}</span></td>
      <td style="text-align:center"><span class="qty-val">${it.quantity}</span></td>
      <td style="color:var(--t2)">${it.unit}</td>
      <td style="color:var(--t2);font-size:12px">${it.location||'—'}</td>
      <td><span class="b b-${it.condition.toLowerCase()}">${it.condition}</span></td>
      <td style="font-size:11px;color:var(--t3);font-family:'JetBrains Mono',monospace">${fmtDt(it.last_updated)}</td>
      <td>
        <div style="display:flex;gap:5px;flex-wrap:wrap">
          <button class="btn btn-green btn-sm" onclick="openAdj(${it.id},'${esc(it.name)}')">± Stock</button>
          <button class="btn btn-outline btn-sm" onclick="openEdit(${it.id})">✏️ Edit</button>
          <button class="btn btn-red btn-sm" onclick="delItem(${it.id},'${esc(it.name)}')">🗑️</button>
        </div>
      </td>
    </tr>`).join('')||'<tr><td colspan="9" class="empty">No items found.</td></tr>';
}

async function loadTxn(){
  const txns=await api('/api/transactions');
  const C={'Stock In':'var(--green)','Stock Out':'var(--red)','Updated':'var(--yellow)','Added':'var(--blue)'};
  document.getElementById('txn-tbody').innerHTML=txns.map(t=>`
    <tr>
      <td style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--t2);white-space:nowrap">${fmtDt(t.timestamp)}</td>
      <td style="font-weight:600">${t.item_name}</td>
      <td><span style="color:${C[t.action]||'var(--t1)'};font-weight:700">${t.action}</span></td>
      <td style="font-family:'JetBrains Mono',monospace;font-weight:600">${t.quantity}</td>
      <td style="color:var(--t2)">${t.performed_by||'Admin'}</td>
      <td style="font-size:12px;color:var(--t3)">${t.notes||'—'}</td>
    </tr>`).join('')||'<tr><td colspan="6" class="empty">No transactions yet.</td></tr>';
}

function openAdd(){
  editId=null;
  document.getElementById('modal-ttl').firstChild.textContent='Add New Item ';
  document.getElementById('modal-sub').textContent='';
  ['f-name','f-qty','f-min','f-loc','f-desc'].forEach(id=>document.getElementById(id).value='');
  document.getElementById('f-cond').value='Good';
  document.getElementById('f-unit').value='pcs';
  if(cats.length) document.getElementById('f-cat').value=cats[0].id;
  document.getElementById('item-modal').classList.add('open');
}

async function openEdit(id){
  editId=id;
  const it=await api(`/api/items/${id}`);
  document.getElementById('modal-ttl').firstChild.textContent='Edit Item ';
  document.getElementById('modal-sub').textContent=`#${id}`;
  document.getElementById('f-name').value=it.name;
  document.getElementById('f-qty').value=it.quantity;
  document.getElementById('f-min').value=it.min_stock;
  document.getElementById('f-loc').value=it.location||'';
  document.getElementById('f-desc').value=it.description||'';
  document.getElementById('f-cond').value=it.condition;
  document.getElementById('f-unit').value=it.unit;
  document.getElementById('f-cat').value=it.category_id;
  document.getElementById('item-modal').classList.add('open');
}

async function saveItem(){
  const name=document.getElementById('f-name').value.trim();
  if(!name){toast('Item name is required.','err');return;}
  const data={
    name,category_id:document.getElementById('f-cat').value,
    quantity:parseInt(document.getElementById('f-qty').value)||0,
    unit:document.getElementById('f-unit').value,
    condition:document.getElementById('f-cond').value,
    min_stock:parseInt(document.getElementById('f-min').value)||5,
    location:document.getElementById('f-loc').value.trim(),
    description:document.getElementById('f-desc').value.trim(),
  };
  if(editId){await api(`/api/items/${editId}`,'PUT',data);toast('Item updated!','ok');}
  else{await api('/api/items','POST',data);toast('Item added!','ok');}
  closeModal('#item-modal');refresh();
}

async function delItem(id,name){
  if(!confirm(`Delete "${name}"? This cannot be undone.`)) return;
  await api(`/api/items/${id}`,'DELETE');
  toast(`"${name}" deleted.`,'inf');refresh();
}

function openAdj(id,name){
  adjId=id;
  document.getElementById('adj-sub').textContent=`— ${name}`;
  document.getElementById('adj-qty').value=1;
  document.getElementById('adj-notes').value='';
  document.getElementById('adj-by').value='';
  document.getElementById('adj-action').value='add';
  document.getElementById('adj-modal').classList.add('open');
}

async function doAdjust(){
  const action=document.getElementById('adj-action').value;
  const qty=parseInt(document.getElementById('adj-qty').value)||1;
  const notes=document.getElementById('adj-notes').value;
  const by=document.getElementById('adj-by').value||'Admin';
  const res=await api(`/api/items/${adjId}/adjust`,'POST',{action,quantity:qty,notes,performed_by:by});
  toast(`Stock ${action==='add'?'added':'removed'}: ${qty} unit(s). New total: ${res.new_quantity}.`,'ok');
  closeModal('#adj-modal');refresh();
}

function closeModal(sel){document.querySelector(sel).classList.remove('open');}

function refresh(){
  if(curPage==='dashboard')    loadDash();
  if(curPage==='inventory')    loadInventory();
  if(curPage==='transactions') loadTxn();
}

function fmtDt(s){
  if(!s) return '—';
  const d=new Date(s.replace(' ','T'));
  return d.toLocaleDateString('en-PH',{month:'short',day:'numeric',year:'numeric'})+' '+
         d.toLocaleTimeString('en-PH',{hour:'2-digit',minute:'2-digit'});
}
function esc(s){return(s||'').replace(/'/g,"\\'");}

function toast(msg,type='inf'){
  const ic={ok:'✅',err:'❌',inf:'ℹ️'};
  const el=document.createElement('div');
  el.className=`toast ${type}`;
  el.innerHTML=`<span>${ic[type]}</span><span>${msg}</span>`;
  document.getElementById('toasts').appendChild(el);
  setTimeout(()=>el.remove(),3800);
}

async function exportPDF(){
  const btn=document.getElementById('pdf-btn');
  btn.disabled=true; btn.textContent='⏳ Generating…';
  try{
    const a=document.createElement('a');
    a.href='/api/export/pdf';
    a.download='';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    toast('PDF export started!','ok');
  }catch(e){toast('Export failed.','err');}
  setTimeout(()=>{btn.disabled=false;btn.textContent='📄 Export PDF';},2000);
}
async function init(){await loadCats();loadDash();}
init();
</script>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    init_db()
    # Auto-create images folder if missing
    os.makedirs(IMGDIR, exist_ok=True)
    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║  SAN JOSE LITEX SENIOR HIGH SCHOOL               ║")
    print("║  Inventory Management System                      ║")
    print("╠══════════════════════════════════════════════════╣")
    print("║  ✅  Database ready  (sjl_inventory.db)           ║")
    print(f"║  🖼️   Images folder : {IMGDIR[:30]}  ║")
    print("║  🚀  Server running at:                           ║") 
    print("║      http://127.0.0.1:5000                        ║")
    print("║                                                    ║")
    print("║  🔐  Login Credentials:                           ║")
    print("║      Username : ADMIN                             ║")
    print("║      Password : 123                               ║")
    print("║                                                    ║")
    print("║  Press CTRL+C to stop the server                  ║")
    print("╚══════════════════════════════════════════════════╝")
    print()
    app.run(debug=False, port=5000)