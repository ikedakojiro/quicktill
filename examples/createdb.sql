/* Create tables and reference data for the till software */

CREATE TABLE businesses (
	business int NOT NULL PRIMARY KEY,
	name varchar(80),
	abbrev varchar(20),
	address varchar(200),
	vatno varchar(30)
	);
COPY businesses FROM stdin;
1	Individual Pubs Limited	IPL	Unit 111, Norman Industrial Estate\\nCambridge Road\\nMilton\\nCambridge CB24 6AT	783 9983 50
\.

CREATE TABLE vat (
	band char(1) NOT NULL PRIMARY KEY,
	rate numeric(5,2) NOT NULL,
	business int NOT NULL REFERENCES businesses(business)
	);
COPY vat FROM stdin;
A	17.5	1
\.

CREATE TABLE vatrates (
	band CHAR(1) NOT NULL REFERENCES vat(band),
	rate NUMERIC(5,2) NOT NULL,
	business INT NOT NULL REFERENCES businesses(business),
	active DATE NOT NULL,
	PRIMARY KEY (band,active));
COPY vatrates FROM stdin;
A	17.5	1	2001-01-01
A	15.0	1	2008-12-01
A	17.5	1	2010-01-01
A	20.0	1	2011-01-04
\.

CREATE OR REPLACE FUNCTION vatrate(CHAR(1),DATE) RETURNS NUMERIC(5,2) AS
'SELECT COALESCE(
 (SELECT rate FROM vatrates WHERE band=$1 AND active<=$2 AND active=
  (SELECT MAX(active) FROM vatrates WHERE band=$1 AND active<=$2)),
 (SELECT rate FROM vat WHERE band=$1));'
LANGUAGE SQL
STABLE
RETURNS NULL ON NULL INPUT;
CREATE OR REPLACE FUNCTION business(CHAR(1),DATE) RETURNS INT AS
'SELECT COALESCE(
 (SELECT business FROM vatrates WHERE band=$1 AND active<=$2 AND active=
  (SELECT MAX(active) FROM vatrates WHERE band=$1 AND active<=$2)),
 (SELECT business FROM vat WHERE band=$1));'
LANGUAGE SQL
STABLE
RETURNS NULL ON NULL INPUT;

CREATE TABLE paytypes (
	paytype varchar(8) NOT NULL PRIMARY KEY,
	description varchar(10) NOT NULL
	);
COPY paytypes FROM stdin;
CASH	Cash
CARD	Card
\.

/* As well as a start and end time, sessions have an accounting date.  This
   is to cope with sessions being closed late (eg. subsequent date) or
   started early.  In the accounts, the session takings will be recorded
   against the session date. */
CREATE SEQUENCE sessions_seq START WITH 1;
CREATE TABLE sessions (
	sessionid int NOT NULL DEFAULT nextval('sessions_seq') PRIMARY KEY,
	starttime timestamp NOT NULL DEFAULT now(),
	endtime timestamp,
	sessiondate date NOT NULL
	);

CREATE TABLE sessiontotals (
	sessionid int NOT NULL REFERENCES sessions(sessionid),
	paytype varchar(8) NOT NULL REFERENCES paytypes(paytype),
	amount numeric(10,2) NOT NULL,
	UNIQUE(sessionid,paytype)
	);

/* transactions.ref is used where one transaction refers to another, eg.
   for closing a tab in a later session (someone forgets to take their
   card, session can't be closed until all transactions are closed) */
CREATE SEQUENCE transactions_seq;
CREATE TABLE transactions (
	transid int NOT NULL PRIMARY KEY,
	sessionid int REFERENCES sessions(sessionid), /* Null sessionid is
		used when transactions are held over from one session to
		the next - eg. when credit card has been left behind */
	notes varchar(60), /* Used to note names on tabs, etc. */
	closed boolean NOT NULL DEFAULT false
	);

/* Negative cash payments represent cashback/change */
CREATE SEQUENCE payments_seq START WITH 1;
CREATE TABLE payments (
        paymentid int NOT NULL PRIMARY KEY DEFAULT nextval('payments_seq'),
	transid int NOT NULL REFERENCES transactions(transid),
	amount numeric(10,2) NOT NULL,
	paytype varchar(8) NOT NULL REFERENCES paytypes(paytype),
	ref varchar(16),
	time timestamp NOT NULL DEFAULT now()
	);

CREATE TABLE pingapint (
	paymentid int NOT NULL PRIMARY KEY REFERENCES payments(paymentid),
	amount numeric(10,2) NOT NULL,
	vid int NOT NULL,
	json_data TEXT NOT NULL,
	reimbursed DATE
	);

CREATE TABLE departments (
	dept int NOT NULL PRIMARY KEY,
	description varchar(20) NOT NULL,
	vatband char(1) NOT NULL REFERENCES vat(band)
	);
COPY departments FROM stdin;
1	Real Ale	A
2	Keg	A
3	Real Cider	A
4	Spirits	A
5	Snacks	A
6	Bottles	A
7	Soft Drinks	A
8	Misc	A
9	Wine	A
10	Food	A
11	Hot Drinks	A
\.

CREATE TABLE transcodes (
	transcode char(1) NOT NULL PRIMARY KEY,
	description varchar(20) NOT NULL
	);
COPY transcodes FROM stdin;
S	Sale
V	Void
C	Cancelled
\.

CREATE SEQUENCE translines_seq;
CREATE TABLE translines (
	translineid int NOT NULL PRIMARY KEY,
	transid int NOT NULL REFERENCES transactions(transid),
	items int NOT NULL, /* Number of items sold in line, for receipts */
	amount numeric(10,2) NOT NULL,
	dept int NOT NULL REFERENCES departments(dept),
	source varchar, /* for till use, eg. vc number */
	stockref int, /* advisory link to stock sale link */
	transcode char(1) NOT NULL REFERENCES transcodes(transcode),
	time timestamp NOT NULL DEFAULT now(),
	text text /* descriptive text for the line, eg. food order */
	);

/* Below here is stock control information */

CREATE SEQUENCE suppliers_seq START WITH 5;
CREATE TABLE suppliers (
	supplierid int NOT NULL PRIMARY KEY,
	name varchar(60) NOT NULL,
	tel varchar(20),
	email varchar(60)
	);
COPY suppliers FROM stdin;
1	Initial part supply	\N	\N
2	Initial supply	\N	\N
3	Milton Brewery	01223 226198	richard@miltonbrewery.co.uk
4	Beer Seller	01733 230167	
\.

CREATE SEQUENCE deliveries_seq START WITH 1;
CREATE TABLE deliveries (
	deliveryid int NOT NULL PRIMARY KEY,
	supplierid int NOT NULL REFERENCES suppliers(supplierid),
	docnumber varchar(40),
	date date NOT NULL DEFAULT now(),
	checked boolean NOT NULL DEFAULT false
	);

/* Types of unit, eg. pint (liquid), ml (liquid), bag, packet, etc. */
CREATE TABLE unittypes (
	unit varchar(10) NOT NULL PRIMARY KEY,
	name varchar(30) NOT NULL
	);
COPY unittypes FROM stdin;
pt	pint
25ml	25ml
50ml	50ml
pkt	packet
bottle	bottle
\.

/* Containers that stock comes in.  Firkin, kil, 24-pack card, box, etc. */
CREATE TABLE stockunits (
	stockunit varchar(8) NOT NULL PRIMARY KEY,
	name varchar(30) NOT NULL,
	unit varchar(10) NOT NULL REFERENCES unittypes(unit),
	size numeric(5,1) NOT NULL /* how many pints, packs, etc. */
	);
COPY stockunits FROM stdin;
pin	Pin	pt	36
tub	5 gal tub	pt	40
keg30l	30l keg	pt	52.8
firkin	Firkin	pt	72
plfirkin	Plastic Firkin	pt	75
ten	Ten gal cask	pt	80
eleven	Eleven gal cask	pt	88
kil	Kilderkin	pt	144
barrel	Barrel	pt	288
card12	12 pack card	pkt	12
card18	18 pack card	pkt	18
card20	20 pack card	pkt	20
card24	24 pack card	pkt	24
box12	12 pack box	pkt	12
box20	20 pack box	pkt	20
box30	30 pack box	pkt	30
box32	32 pack box	pkt	32
box36	36 pack box	pkt	36
box44	44 pack box	pkt	44
box48	48 pack box	pkt	48
box50	50 pack box	pkt	50
70clsm	70cl bottle, 25ml measures	25ml	28
75clsm	75cl bottle, 25ml measures	25ml	30
1lsm	1l bottle, 25ml measures	25ml	40
1.5lsm	1.5l bottle, 25ml measures	25ml	60
75cldm	75cl bottle, 50ml measures	50ml	15
1ldm	1l bottle, 50ml measures	50ml	20
1.5ldm	1.5l bottle, 50ml measures	50ml	30
crate12	12 bottle crate	bottle	12
crate20	20 bottle crate	bottle	20
crate24	24 bottle crate	bottle	24
\.

CREATE TABLE stocktypes (
	stocktype int NOT NULL PRIMARY KEY,
	dept int NOT NULL REFERENCES departments(dept),
	manufacturer varchar(30) NOT NULL, /* Brewery name for beers */
	name varchar(30) NOT NULL, /* Beer name for beers */
	shortname varchar(25) NOT NULL, /* Printed on receipts */
	abv numeric(3,1), /* For alcoholic products */
	unit varchar(10) NOT NULL REFERENCES unittypes(unit)
	);
CREATE SEQUENCE stocktypes_seq;

CREATE TABLE stockfinish (
	finishcode varchar(8) NOT NULL PRIMARY KEY,
	description varchar(50) NOT NULL
	);
COPY stockfinish FROM stdin;
empty	All gone
credit	Returned for credit
turned	Turned sour / off taste
ood	Out of date
\.

CREATE TABLE stock (
	stockid int NOT NULL PRIMARY KEY, /* Gets written on the stock item */
	deliveryid int NOT NULL REFERENCES deliveries(deliveryid),
	stocktype int NOT NULL REFERENCES stocktypes(stocktype),
	stockunit varchar(8) NOT NULL REFERENCES stockunits(stockunit),
	costprice numeric(7,2), /* ex VAT */
	saleprice numeric(5,2) NOT NULL, /* inc VAT */
	onsale timestamp,
	finished timestamp,
	finishcode varchar(8) REFERENCES stockfinish(finishcode),
	bestbefore date
	);
CREATE SEQUENCE stock_seq;

/* Annotations are made against stock items for various events (depending
   on the stock type).  These are not necessary for the operation of
   the till, but can be useful when analysing stock usage. */
CREATE TABLE annotation_types (
	atype varchar(8) NOT NULL PRIMARY KEY,
	description varchar(20) NOT NULL
	);
COPY annotation_types FROM stdin;
location	Location
start	Put on sale
stop	Removed from sale
vent	Vented
memo	Memo
\.
CREATE SEQUENCE stock_annotation_seq;
CREATE TABLE stock_annotations (
        id int NOT NULL PRIMARY KEY DEFAULT nextval('stock_annotation_seq'),
	stockid int NOT NULL REFERENCES stock(stockid),
	atype varchar(8) NOT NULL REFERENCES annotation_types(atype),
	time timestamp NOT NULL DEFAULT now(),
	text varchar(60) NOT NULL
	);

/* Reasons for stock removal, eg. sale, out-of-date, waste, etc. */
CREATE TABLE stockremove (
	removecode varchar(8) NOT NULL PRIMARY KEY,
	reason varchar(80)
	);
COPY stockremove FROM stdin;
sold	Sold
pullthru	Pulled through
ood	Out of date
taste	Bad taste
taster	Free taster
cellar	Cellar work
damaged	Damaged
freebie	Free drink
missing	Gone missing
driptray	Drip tray
\.

/* One entry is made here every time stock is removed.  This table is
   referred to by translines(stockref). */
CREATE TABLE stockout (
	stockoutid int NOT NULL PRIMARY KEY,
	stockid int NOT NULL REFERENCES stock(stockid),
	qty numeric(5,1) NOT NULL,
	removecode varchar(8) NOT NULL REFERENCES stockremove(removecode),
	translineid int, /* translines(translineid) but would be circular ref */
	time timestamp NOT NULL DEFAULT now()
	);
CREATE SEQUENCE stockout_seq START WITH 1;

CREATE TABLE stocklines (
	stocklineid int NOT NULL PRIMARY KEY,
	name varchar(30) NOT NULL UNIQUE,
	location varchar(20) NOT NULL,
	capacity int,
	dept int NOT NULL REFERENCES departments(dept),
	pullthru numeric(5,1)
	);
CREATE SEQUENCE stocklines_seq START WITH 100;

/* All stock currently on sale. */
/* Check that stock->delivery.checked is true! */
CREATE TABLE stockonsale (
	stocklineid int NOT NULL REFERENCES stocklines(stocklineid),
	stockid int REFERENCES stock(stockid) UNIQUE,
	displayqty int
	);

/* This table stores details of the mapping from keycodes/keyboard layout
(the database may be supporting multiple terminals with different layouts)
to lines.  If multiple entries are present for a key then a menu is displayed
offering further keypresses to select the line. */
CREATE TABLE keyboard (
	layout int NOT NULL,
	keycode varchar(20) NOT NULL,
	menukey varchar(20) NOT NULL,
	stocklineid int NOT NULL, /* Really needs REFERENCES! */
	qty numeric(5,2) NOT NULL,
	PRIMARY KEY (layout,keycode,menukey)
	);

CREATE TABLE keycaps (
	layout int NOT NULL,
	keycode varchar(20) NOT NULL,
	keycap varchar(30),
	PRIMARY KEY (layout,keycode)
	);

/* Record which stock types have been put on sale on which lines, to assist
   with sorting the 'Use Stock' menu */
CREATE TABLE stockline_stocktype_log (
       stocklineid int NOT NULL REFERENCES stocklines(stocklineid) ON DELETE CASCADE,
       stocktype int NOT NULL REFERENCES stocktypes(stocktype) ON DELETE CASCADE,
       PRIMARY KEY (stocklineid,stocktype)
       );

/* Till users; this table is used for the "lock screen" function.  It
   is _not_ for security. */
CREATE TABLE users (
       code char(2) NOT NULL PRIMARY KEY,
       name varchar(30) NOT NULL
       );

CREATE OR REPLACE RULE ignore_duplicate_stockline_types AS
       ON INSERT TO stockline_stocktype_log
       WHERE (NEW.stocklineid,NEW.stocktype)
       IN (SELECT stocklineid,stocktype FROM stockline_stocktype_log)
       DO INSTEAD NOTHING;

/* Useful views for queries */
CREATE VIEW stockinfo AS
	SELECT s.stockid,st.stocktype,s.deliveryid,
		st.dept,dep.description AS deptname,
		st.manufacturer,st.name,st.shortname,st.abv,st.unit,
		ut.name AS unitname,
		su.stockunit,su.name AS sunitname,su.size,s.costprice,
		s.saleprice,s.onsale,s.finished,
		s.finishcode,sf.description AS finishdescription,
		s.bestbefore,
		sup.name AS suppliername, d.date AS deliverydate,
		d.docnumber AS deliverynote,d.checked AS deliverychecked,
		(SELECT sum(so.qty) FROM stockout so
			WHERE so.stockid=s.stockid) AS used,
		(SELECT sum(so.qty) FROM stockout so
			WHERE so.stockid=s.stockid AND so.removecode 
				IN ('sold','freebie'))
			AS sold
	FROM stock s
	LEFT JOIN stocktypes st ON s.stocktype=st.stocktype
	LEFT JOIN departments dep ON st.dept=dep.dept
	LEFT JOIN stockunits su ON s.stockunit=su.stockunit
	LEFT JOIN unittypes ut ON su.unit=ut.unit
	LEFT JOIN deliveries d ON s.deliveryid=d.deliveryid
	LEFT JOIN suppliers sup ON d.supplierid=sup.supplierid
	LEFT JOIN stockfinish sf ON s.finishcode=sf.finishcode;

/* This rule refers to the stockinfo view, so must be created after it. */
CREATE OR REPLACE RULE log_stocktype AS ON INSERT TO stockonsale
       DO ALSO
       INSERT INTO stockline_stocktype_log VALUES
       (NEW.stocklineid,(SELECT stocktype FROM stock
       	WHERE stock.stockid=NEW.stockid));

/* Stock id, qty in container, unitname, amount used, amount sold, amount
   pulled through */
CREATE VIEW stockqty AS
	SELECT s.stockid,su.size,ut.name AS unitname,
		sum(so.qty) AS qtyused,
		sum(CASE WHEN so.removecode='sold' THEN so.qty ELSE 0.0 END)
			AS qtysold,
		sum(CASE WHEN so.removecode='pullthru' THEN so.qty ELSE 0.0 END)
			AS qtypullthru
	FROM stock s
	INNER JOIN stocktypes st ON s.stocktype=st.stocktype
	INNER JOIN stockunits su ON s.stockunit=su.stockunit
	INNER JOIN unittypes ut ON su.unit=ut.unit
	LEFT JOIN stockout so ON s.stockid=so.stockid
	GROUP BY s.stockid,su.size,unitname;

/* Create the circular reference between translines and stockout here?
translines.stockref references stockout.stockoutid
stockout.translineid references translines.translineid

Set so that references are only checked at end of transaction.
*/

/* The businesstotals view is used by the tillweb module */
CREATE VIEW businesstotals AS
 SELECT b.abbrev, s.sessionid, s.sessiondate, sum(tl.items::numeric * tl.amount) AS sum
   FROM sessions s
   JOIN transactions t ON t.sessionid = s.sessionid
   JOIN translines tl ON t.transid = tl.transid
   LEFT JOIN departments d ON tl.dept = d.dept
   LEFT JOIN vat ON vat.band::text = d.vatband::text
   LEFT JOIN businesses b ON b.business = vat.business
  GROUP BY b.abbrev, s.sessionid, s.sessiondate;


CREATE RULE max_one_open AS ON INSERT TO sessions
	WHERE (SELECT COUNT(*) FROM sessions WHERE endtime IS NULL)>0
	DO INSTEAD NOTHING;
CREATE RULE may_not_change AS ON UPDATE TO sessions
	WHERE OLD.endtime IS NOT NULL
	DO INSTEAD NOTHING;

CREATE RULE may_not_reopen AS ON UPDATE TO transactions
	WHERE OLD.closed=true
	DO INSTEAD NOTHING;
CREATE RULE close_only_if_balanced AS ON UPDATE TO transactions
	WHERE NEW.closed=true AND
		(SELECT sum(amount*items) FROM translines
			WHERE transid=NEW.transid)!=
		(SELECT sum(amount) FROM payments
			WHERE transid=NEW.transid)
	DO INSTEAD NOTHING;
CREATE RULE close_only_if_nonzero AS ON UPDATE TO transactions
	WHERE NEW.closed=true AND
		((SELECT count(*) FROM translines WHERE transid=NEW.transid)=0
		OR (SELECT count(*) FROM payments WHERE transid=NEW.transid)=0)
	DO INSTEAD NOTHING;
CREATE RULE create_only_if_session_open AS ON INSERT TO transactions
	WHERE (SELECT endtime FROM sessions WHERE sessionid=NEW.sessionid)
		IS NOT NULL
	DO INSTEAD NOTHING;

CREATE RULE no_add_to_closed AS ON INSERT TO payments
	WHERE (SELECT closed FROM transactions
		WHERE transid=NEW.transid)=true
	DO INSTEAD NOTHING;

CREATE RULE no_add_to_closed AS ON INSERT TO translines
	WHERE (SELECT closed FROM transactions
		WHERE transid=NEW.transid)=true
	DO INSTEAD NOTHING;

/* The translines and payments tables are routinely scanned based on
transaction ID, so we'd better index them on those. */

CREATE INDEX translines_transid_key ON translines (transid);
CREATE INDEX payments_transid_key ON payments (transid);
CREATE INDEX transactions_sessionid_key ON transactions (sessionid);
CREATE INDEX stock_annotations_stockid_key ON stock_annotations (stockid);

/* The "stock_extrainfo" function in td.py reads the stockout table
selecting on stock ID.  This could probably be speeded using an index. */

CREATE INDEX stockout_stockid_key ON stockout (stockid);

/* The web "find free drinks on this day" function is speeded up
considerably by an index on stockout.time::date */

CREATE INDEX stockout_date_key ON stockout ( (time::date) );

/* The "stock_sellmore" function in td.py updates the stockout table
by selecting on translineid.  This could probably be speeded using an index. */
CREATE INDEX stockout_translineid_key ON stockout (translineid);

/* The tillweb software finds this index helpful when calculating how
much was taken in the last two weeks; it lets the query exclude a large
percentage of the translines table from consideration. */

CREATE INDEX translines_time_key ON translines (time);

CREATE SEQUENCE foodorder_seq;