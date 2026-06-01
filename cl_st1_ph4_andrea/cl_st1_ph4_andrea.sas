/* CCA - CL_St1_Ph4_andrea_CCA */

/* Match this to the actual folder in SAS OnDemand */
%LET project = cl_st1_ph4_andrea_CCA;
%LET myfolder = &project;

/* Replace with your SAS user ID */
%LET sasusername = u63529080;

/* Importing the data set */
PROC IMPORT DATAFILE="/home/&sasusername/&myfolder/tv_commercials_cca.tsv"
            OUT=tv_commercials_cca
            DBMS=TAB
            REPLACE;
   GETNAMES=YES;
   GUESSINGROWS=MAX;
RUN;

PROC CONTENTS DATA=work.tv_commercials_cca;
RUN;

PROC MEANS DATA=work.tv_commercials_cca N NMISS MEAN STD MIN MAX;
    VAR ver1 ver2 ver3 ver4 ver5 ver6 ver7 ver8
        vis1 vis2 vis3 vis4 vis5 vis6 vis7 vis8;
RUN;

/* CCA */

%LET resultsfile = tv_commercials_cca-results.html;

ODS HTML FILE="/home/&sasusername/&myfolder/&resultsfile"
         STYLE=HTMLBlue;

TITLE "CCA for &project";
ODS NOPROCTITLE;
ODS GRAPHICS / IMAGEMAP=ON;

PROC CANCORR DATA=work.tv_commercials_cca
             OUT=tv_commercials_cca_scores;
    VAR ver1 ver2 ver3 ver4 ver5 ver6 ver7 ver8;
    WITH vis1 vis2 vis3 vis4 vis5 vis6 vis7 vis8;
RUN;
QUIT;

ODS HTML CLOSE;

PROC EXPORT DATA=work.tv_commercials_cca_scores
            OUTFILE="/home/&sasusername/&myfolder/tv_commercials_cca_scores.tsv"
            DBMS=TAB
            REPLACE;
RUN;

/* ZIP OUTPUT FILES */

%let addcntzip = /home/u63529080/zip/output_&project..zip;

FILENAME temp "&addcntzip";

DATA _NULL_;
  rc=FDELETE('temp');
RUN;

data filelist;
run;

data filelist;
  length root dname $ 2048 filename $ 256 dir level 8;
  input root;
  retain filename dname ' ' level 0 dir 1;
cards4;
/home/u63529080/cl_st1_ph4_andrea_CCA
;;;;
run;

data filelist;
  modify filelist;
  rc1=filename('tmp',catx('/',root,dname,filename));
  rc2=dopen('tmp');
  dir = 1 & rc2;

  if dir then do;
      dname=catx('/',dname,filename);
      filename=' ';
  end;

  replace;

  if dir;

  level=level+1;

  do i=1 to dnum(rc2);
    filename=dread(rc2,i);
    output;
  end;

  rc3=dclose(rc2);
run;

proc sort data=filelist;
  by root dname filename;
run;

proc print data=filelist;
run;

data _null_;

  set filelist;

  if dir=0;

  rc1=filename("in" , catx('/',root,dname,filename), "disk", "lrecl=1 recfm=n");
  rc1txt=sysmsg();

  rc2=filename(
      "out",
      "&addcntzip.",
      "ZIP",
      "lrecl=1 recfm=n member='" !! catx('/',dname,filename) !! "'"
  );
  rc2txt=sysmsg();

  do _N_ = 1 to 6;
    rc3=fcopy("in","out");
    rc3txt=sysmsg();

    if fexist("out") then leave;
    else sleeprc=sleep(0.5,1);
  end;

  rc4=fexist("out");
  rc4txt=sysmsg();

  put _N_ @12 (rc:) (=);

run;


/* delete all png, html, tsv, and csv files after zipping */

%let path=&whereisit/&myfolder;

FILENAME _folder_ "%bquote(&path.)";

data filenames(keep=memname);
  handle=dopen( '_folder_' );

  if handle > 0 then do;
    count=dnum(handle);

    do i=1 to count;
      memname=dread(handle,i);

      if scan(memname, 2, '.')='png'
      OR scan(memname, 2, '.')='html'
      OR scan(memname, 2, '.')='tsv'
      OR scan(memname, 2, '.')='csv'
      then output filenames;
    end;
  end;

  rc=dclose(handle);
run;

filename _folder_ clear;

data _null_;
set filenames;
fname = 'todelete';
rc = filename(fname, quote(cats("&path",'/',memname)));
rc = fdelete(fname);
rc = filename(fname);
run;