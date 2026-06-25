/* ANOVA - CL_St1_Ph5_andrea_ANOVA */

/*
   Phase 5 objective:
   Conduct ANOVAs to detect diachronic variation in:
   1. verbal discourses;
   2. visual discourses;
   3. cross-modal discourses.

   Input:
   tv_commercials_cca_scores.tsv

   This file is expected to contain:
   - file_id
   - group_filename
   - decade
   - verbal factor scores: ver1-ver8
   - visual factor scores: vis1-vis8
   - canonical variate scores: V1-V8 and W1-W8

   Only canonical dimensions 1-7 are used for cross-modal ANOVAs,
   because only the first seven canonical dimensions are statistically significant.
*/

/* Match this to the actual folder in SAS OnDemand */
%LET project = cl_st1_ph5_andrea_ANOVA;
%LET myfolder = &project;

/* Replace with your SAS user ID */
%LET sasusername = u63529080;
%LET whereisit = /home/&sasusername;

/* Input file exported from Phase 4 CCA */
%LET inputfile = tv_commercials_cca_scores.tsv;

/* Importing the Phase 4 CCA score data set */
PROC IMPORT DATAFILE="&whereisit/&myfolder/&inputfile"
            OUT=tv_commercials_cca_scores
            DBMS=TAB
            REPLACE;
   GETNAMES=YES;
   GUESSINGROWS=MAX;
RUN;

/* Inspect imported data */
PROC CONTENTS DATA=work.tv_commercials_cca_scores;
RUN;

/* Check decade distribution */
PROC FREQ DATA=work.tv_commercials_cca_scores;
    TABLES decade / MISSING;
RUN;

/* Descriptive statistics for verbal, visual, and canonical scores */
PROC MEANS DATA=work.tv_commercials_cca_scores N NMISS MEAN STD MIN MAX;
    CLASS decade;
    VAR ver1 ver2 ver3 ver4 ver5 ver6 ver7 ver8
        vis1 vis2 vis3 vis4 vis5 vis6 vis7 vis8
        V1 V2 V3 V4 V5 V6 V7
        W1 W2 W3 W4 W5 W6 W7;
RUN;

/* Overall descriptive statistics without decade grouping */
PROC MEANS DATA=work.tv_commercials_cca_scores N NMISS MEAN STD MIN MAX;
    VAR ver1 ver2 ver3 ver4 ver5 ver6 ver7 ver8
        vis1 vis2 vis3 vis4 vis5 vis6 vis7 vis8
        V1 V2 V3 V4 V5 V6 V7
        W1 W2 W3 W4 W5 W6 W7;
RUN;

/* Main HTML output */
%LET resultsfile = tv_commercials_phase5_anova-results.html;

ODS HTML FILE="&whereisit/&myfolder/&resultsfile"
         STYLE=HTMLBlue;

TITLE "Phase 5 ANOVAs for &project";
ODS NOPROCTITLE;
ODS GRAPHICS / IMAGEMAP=ON;

/* ------------------------------------------------------------------ */
/* 1. Verbal discourse ANOVAs                                          */
/* ------------------------------------------------------------------ */

TITLE2 "Verbal discourse ANOVAs: ver1-ver8 by decade";

ODS OUTPUT ModelANOVA=anova_verbal_model;
ODS OUTPUT OverallANOVA=anova_verbal_overall;
ODS OUTPUT LSMeans=lsmeans_verbal;
ODS OUTPUT Diffs=diffs_verbal;

ODS EXCLUDE ALL;

PROC GLM DATA=work.tv_commercials_cca_scores;
    CLASS decade;
    MODEL ver1 ver2 ver3 ver4 ver5 ver6 ver7 ver8 = decade;
    MEANS decade / HOVTEST=LEVENE;
    LSMEANS decade / PDIFF ADJUST=TUKEY;
RUN;
QUIT;

ODS EXCLUDE NONE;
ODS OUTPUT CLOSE;

/* ------------------------------------------------------------------ */
/* 2. Visual discourse ANOVAs                                          */
/* ------------------------------------------------------------------ */

TITLE2 "Visual discourse ANOVAs: vis1-vis8 by decade";

ODS OUTPUT ModelANOVA=anova_visual_model;
ODS OUTPUT OverallANOVA=anova_visual_overall;
ODS OUTPUT LSMeans=lsmeans_visual;
ODS OUTPUT Diffs=diffs_visual;

ODS EXCLUDE ALL;

PROC GLM DATA=work.tv_commercials_cca_scores;
    CLASS decade;
    MODEL vis1 vis2 vis3 vis4 vis5 vis6 vis7 vis8 = decade;
    MEANS decade / HOVTEST=LEVENE;
    LSMEANS decade / PDIFF ADJUST=TUKEY;
RUN;
QUIT;

ODS EXCLUDE NONE;
ODS OUTPUT CLOSE;

/* ------------------------------------------------------------------ */
/* 3. Cross-modal discourse ANOVAs                                     */
/* ------------------------------------------------------------------ */

/*
   Cross-modal discourse scores are represented by canonical variate
   scores from PROC CANCORR.

   V1-V7 = verbal-side canonical variate scores.
   W1-W7 = visual-side canonical variate scores.

   Only dimensions 1-7 are included because they are statistically significant.
*/

TITLE2 "Cross-modal discourse ANOVAs: canonical variate scores V1-W7 by decade";

ODS OUTPUT ModelANOVA=anova_crossmodal_model;
ODS OUTPUT OverallANOVA=anova_crossmodal_overall;
ODS OUTPUT LSMeans=lsmeans_crossmodal;
ODS OUTPUT Diffs=diffs_crossmodal;

ODS EXCLUDE ALL;

PROC GLM DATA=work.tv_commercials_cca_scores;
    CLASS decade;
    MODEL V1 W1
          V2 W2
          V3 W3
          V4 W4
          V5 W5
          V6 W6
          V7 W7 = decade;
    MEANS decade / HOVTEST=LEVENE;
    LSMEANS decade / PDIFF ADJUST=TUKEY;
RUN;
QUIT;

ODS EXCLUDE NONE;
ODS OUTPUT CLOSE;

/* ------------------------------------------------------------------ */
/* 4. Optional composite cross-modal scores                            */
/* ------------------------------------------------------------------ */

/*
   This section creates one composite score per canonical dimension by
   averaging the verbal-side and visual-side canonical variate scores.

   These variables are useful if you want one ANOVA per cross-modal
   dimension rather than separate Vn and Wn tests.

   Because Vn and Wn are already canonical variate scores from the same
   canonical pair, the composite score should be interpreted as a derived
   cross-modal index.
*/

DATA tv_commercials_phase5_scores;
    SET work.tv_commercials_cca_scores;

    cross1 = MEAN(V1, W1);
    cross2 = MEAN(V2, W2);
    cross3 = MEAN(V3, W3);
    cross4 = MEAN(V4, W4);
    cross5 = MEAN(V5, W5);
    cross6 = MEAN(V6, W6);
    cross7 = MEAN(V7, W7);
RUN;

TITLE2 "Derived cross-modal composite ANOVAs: cross1-cross7 by decade";

ODS OUTPUT ModelANOVA=anova_crossmodal_composite_model;
ODS OUTPUT OverallANOVA=anova_crossmodal_composite_overall;
ODS OUTPUT LSMeans=lsmeans_crossmodal_composite;
ODS OUTPUT Diffs=diffs_crossmodal_composite;

ODS EXCLUDE ALL;

PROC GLM DATA=work.tv_commercials_phase5_scores;
    CLASS decade;
    MODEL cross1 cross2 cross3 cross4 cross5 cross6 cross7 = decade;
    MEANS decade / HOVTEST=LEVENE;
    LSMEANS decade / PDIFF ADJUST=TUKEY;
RUN;
QUIT;

ODS EXCLUDE NONE;
ODS OUTPUT CLOSE;

/* ------------------------------------------------------------------ */
/* 5. Export analysis data and ANOVA result tables                     */
/* ------------------------------------------------------------------ */

TITLE2 "Exported Phase 5 data and ANOVA tables";

PROC EXPORT DATA=work.tv_commercials_phase5_scores
            OUTFILE="&whereisit/&myfolder/tv_commercials_phase5_scores.tsv"
            DBMS=TAB
            REPLACE;
RUN;

/* Model ANOVA tables */

PROC EXPORT DATA=work.anova_verbal_model
            OUTFILE="&whereisit/&myfolder/anova_verbal_model.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.anova_visual_model
            OUTFILE="&whereisit/&myfolder/anova_visual_model.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.anova_crossmodal_model
            OUTFILE="&whereisit/&myfolder/anova_crossmodal_model.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.anova_crossmodal_composite_model
            OUTFILE="&whereisit/&myfolder/anova_crossmodal_composite_model.tsv"
            DBMS=TAB
            REPLACE;
RUN;

/* Overall ANOVA tables */

PROC EXPORT DATA=work.anova_verbal_overall
            OUTFILE="&whereisit/&myfolder/anova_verbal_overall.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.anova_visual_overall
            OUTFILE="&whereisit/&myfolder/anova_visual_overall.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.anova_crossmodal_overall
            OUTFILE="&whereisit/&myfolder/anova_crossmodal_overall.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.anova_crossmodal_composite_overall
            OUTFILE="&whereisit/&myfolder/anova_crossmodal_composite_overall.tsv"
            DBMS=TAB
            REPLACE;
RUN;

/* LSMeans tables */

PROC EXPORT DATA=work.lsmeans_verbal
            OUTFILE="&whereisit/&myfolder/lsmeans_verbal.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.lsmeans_visual
            OUTFILE="&whereisit/&myfolder/lsmeans_visual.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.lsmeans_crossmodal
            OUTFILE="&whereisit/&myfolder/lsmeans_crossmodal.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.lsmeans_crossmodal_composite
            OUTFILE="&whereisit/&myfolder/lsmeans_crossmodal_composite.tsv"
            DBMS=TAB
            REPLACE;
RUN;

/* Tukey pairwise-comparison tables */

PROC EXPORT DATA=work.diffs_verbal
            OUTFILE="&whereisit/&myfolder/diffs_verbal.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.diffs_visual
            OUTFILE="&whereisit/&myfolder/diffs_visual.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.diffs_crossmodal
            OUTFILE="&whereisit/&myfolder/diffs_crossmodal.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.diffs_crossmodal_composite
            OUTFILE="&whereisit/&myfolder/diffs_crossmodal_composite.tsv"
            DBMS=TAB
            REPLACE;
RUN;

ODS HTML CLOSE;

/* ------------------------------------------------------------------ */
/* 6. ZIP OUTPUT FILES                                                 */
/* ------------------------------------------------------------------ */

%LET addcntzip = /home/&sasusername/zip/output_&project..zip;

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
/home/u63529080/cl_st1_ph5_andrea_ANOVA
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

/* ------------------------------------------------------------------ */
/* 7. Optional cleanup                                                 */
/* ------------------------------------------------------------------ */

/*
   This cleanup follows the Phase 4 template.
   Comment out this section if you want the HTML and TSV files to remain
   visible in the SAS OnDemand folder after zipping.
*/

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

/* END OF PROGRAMME */