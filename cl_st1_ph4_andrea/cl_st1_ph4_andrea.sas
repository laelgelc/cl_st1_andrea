/* CCA - CL_St1_Ph4_andrea_CCA */

/* Match this to the actual folder in SAS OnDemand */
%LET project = cl_st1_ph4_andrea_CCA;
%LET myfolder = &project;

/* Replace with your SAS user ID */
%LET sasusername = u63529080;
%LET whereisit = /home/&sasusername;

/* Importing the data set */
PROC IMPORT DATAFILE="&whereisit/&myfolder/tv_commercials_cca.tsv"
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
            OUTFILE="&whereisit/&myfolder/tv_commercials_cca_scores.tsv"
            DBMS=TAB
            REPLACE;
RUN;

/* ZIP OUTPUT FILES */

%LET addcntzip = /home/u63529080/zip/output_&project..zip;

FILENAME temp "&addcntzip";

DATA _NULL_;
    rc = FDELETE('temp');
RUN;

DATA filelist;
RUN;

DATA filelist;
    LENGTH root dname $ 2048 filename $ 256 dir level 8;
    INPUT root;
    RETAIN filename dname ' ' level 0 dir 1;
CARDS4;
/home/u63529080/cl_st1_ph4_andrea_CCA
;;;;
RUN;

DATA filelist;
    MODIFY filelist;
    rc1 = FILENAME('tmp', CATX('/', root, dname, filename));
    rc2 = DOPEN('tmp');
    dir = 1 & rc2;

    IF dir THEN DO;
        dname = CATX('/', dname, filename);
        filename = ' ';
    END;

    REPLACE;

    IF dir;

    level = level + 1;

    DO i = 1 TO DNUM(rc2);
        filename = DREAD(rc2, i);
        OUTPUT;
    END;

    rc3 = DCLOSE(rc2);
RUN;

PROC SORT DATA=filelist;
    BY root dname filename;
RUN;

PROC PRINT DATA=filelist;
RUN;

DATA _NULL_;
    SET filelist;

    IF dir = 0;

    rc1 = FILENAME("in", CATX('/', root, dname, filename), "disk", "lrecl=1 recfm=n");
    rc1txt = SYSMSG();

    rc2 = FILENAME(
        "out",
        "&addcntzip.",
        "ZIP",
        "lrecl=1 recfm=n member='" !! CATX('/', dname, filename) !! "'"
    );
    rc2txt = SYSMSG();

    DO _N_ = 1 TO 6;
        rc3 = FCOPY("in", "out");
        rc3txt = SYSMSG();

        IF FEXIST("out") THEN LEAVE;
        ELSE sleeprc = SLEEP(0.5, 1);
    END;

    rc4 = FEXIST("out");
    rc4txt = SYSMSG();

    PUT _N_ @12 (rc:) (=);
RUN;


/* DELETE ALL PNG, HTML, TSV, AND CSV FILES AFTER ZIPPING */

%LET path = &whereisit/&myfolder;

FILENAME _folder_ "%BQUOTE(&path.)";

DATA filenames(KEEP=memname);
    handle = DOPEN('_folder_');

    IF handle > 0 THEN DO;
        count = DNUM(handle);

        DO i = 1 TO count;
            memname = DREAD(handle, i);

            IF SCAN(memname, 2, '.') = 'png'
                OR SCAN(memname, 2, '.') = 'html'
                OR SCAN(memname, 2, '.') = 'tsv'
                OR SCAN(memname, 2, '.') = 'csv'
            THEN OUTPUT filenames;
        END;
    END;

    rc = DCLOSE(handle);
RUN;

FILENAME _folder_ CLEAR;

DATA _NULL_;
    SET filenames;
    fname = 'todelete';
    rc = FILENAME(fname, QUOTE(CATS("&path", '/', memname)));
    rc = FDELETE(fname);
    rc = FILENAME(fname);
RUN;